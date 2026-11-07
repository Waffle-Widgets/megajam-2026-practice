"""Pure-PyTorch stand-in for NATTEN's na2d (2-D neighbourhood attention), for Windows, where NATTEN doesn't build.

Covers only what Pixal3D's NAF feature upsampler (valeoai/NAF) calls:
    na2d(q, k, v, kernel_size=(9, 9), dilation=(dh, dw), stride=1, backend=...)
Tensor layout as in NATTEN >= 0.20: [batch, H, W, heads, head_dim]; the value may have its own head_dim.

Same rules as NATTEN:
- with dilation (dh, dw) the image splits into dh*dw interleaved sub-grids (rows r = a + i*dh, columns c = b + j*dw);
- inside each sub-grid every query attends to the kernel_h x kernel_w neighbours around it, and near an edge the
  window shifts inward instead of padding, so every query always sees a full window;
- softmax scale defaults to head_dim ** -0.5.
There is deliberately no `natten.functional`, so NAF takes its "recent natten" path and calls na2d.
"""
import torch

__version__ = "0.21.0+pytorch-shim"


def _window_index(n, k, device):
    """[n, k] indices of the k neighbours of each of n positions, window clamped to stay inside 0..n-1."""
    start = (torch.arange(n, device=device) - k // 2).clamp(0, n - k)
    return start[:, None] + torch.arange(k, device=device)


def na2d(query, key, value, kernel_size, stride=1, dilation=1, is_causal=False, scale=None, backend=None, **kwargs):
    kh, kw = (kernel_size, kernel_size) if isinstance(kernel_size, int) else tuple(kernel_size)
    dh, dw = (dilation, dilation) if isinstance(dilation, int) else tuple(dilation)
    sh, sw = (stride, stride) if isinstance(stride, int) else tuple(stride)
    causal = is_causal if isinstance(is_causal, bool) else any(is_causal)
    if (sh, sw) != (1, 1) or causal:
        raise NotImplementedError("natten shim: only stride 1, non-causal")
    B, H, W, N, D = query.shape
    Dv = value.shape[-1]
    if H % dh or W % dw:
        raise NotImplementedError(f"natten shim: size {H}x{W} not divisible by dilation {dh}x{dw}")
    h, w = H // dh, W // dw
    if h < kh or w < kw:
        raise ValueError(f"natten shim: sub-grid {h}x{w} smaller than kernel {kh}x{kw}")
    if scale is None:
        scale = D ** -0.5
    dev = query.device

    def split(x):  # [B, H, W, N, C] -> [B*dh*dw, h, w, N, C]
        C = x.shape[-1]
        x = x.reshape(B, h, dh, w, dw, N, C).permute(0, 2, 4, 1, 3, 5, 6)
        return x.reshape(B * dh * dw, h, w, N, C)

    q, k, v = split(query), split(key), split(value)
    rows = _window_index(h, kh, dev)  # [h, kh]
    cols = _window_index(w, kw, dev)  # [w, kw]
    G = q.shape[0]
    out = torch.empty((G, h, w, N, Dv), dtype=query.dtype, device=dev)
    # process sub-grids in chunks so the gathered windows stay around 2 GB (float32)
    per_grid = h * w * kh * kw * N * max(D, Dv)
    chunk = max(1, (1 << 29) // per_grid)
    for g0 in range(0, G, chunk):
        g1 = min(G, g0 + chunk)

        def windows(x):  # [g, h, w, N, C] -> [g, h, w, kh*kw, N, C]
            x = x[g0:g1][:, rows][:, :, :, cols]  # [g, h, kh, w, kw, N, C]
            g, C = x.shape[0], x.shape[-1]
            return x.permute(0, 1, 3, 2, 4, 5, 6).reshape(g, h, w, kh * kw, N, C)

        kk = windows(k).float()
        att = torch.einsum('ghwnd,ghwknd->ghwnk', q[g0:g1].float(), kk) * scale
        del kk
        att = att.softmax(dim=-1)
        vv = windows(v).float()
        out[g0:g1] = torch.einsum('ghwnk,ghwknc->ghwnc', att, vv).to(query.dtype)
        del att, vv
    # back to [B, H, W, N, Dv]
    out = out.reshape(B, dh, dw, h, w, N, Dv).permute(0, 3, 1, 4, 2, 5, 6)
    return out.reshape(B, H, W, N, Dv)
