"""Make pictures with the local image model (ComfyUI + Qwen-Image on M Station's 3090), no Gemini copy-paste.
From the Coreatures project (r244). Use it for reference pictures for Meshy or TRELLIS (full body, plain white
background) and concept art. Pictures land in Art/Refs/gen/ (ignored by git). Pixel-art add-on: --lora
qwen2512_pixel_art.safetensors (off by default here).

    python tools/gen-images.py STEEL-1 WIND-2b            # every prompt code you name, 2 takes each
    python tools/gen-images.py ICE-2a --takes 4 --seed 7   # more takes, a fixed starting seed
    python tools/gen-images.py --text "a pixel art ..."    # any prompt, saved as custom-N.png

Defaults (r244, tuned against Gemini): Qwen-Image-2512 with a pixel-art LoRA at 0.8, cfg 4, 30 steps. Prompts work best
short, plain and positive (say what to draw, not what not to; put unwanted things in --neg), naming the style once:
"16-bit SNES era pixel art sprite sheet, crisp chunky pixels, solid 1-pixel black outline, cel shading with three
hard-edged tones, flat plain dark navy background, lots of empty space between sprites". It takes words literally
("tower shield" drew a tower), so describe shapes ("a tall rectangular shield with a pointed bottom").

It finds each code's prompt (the quoted '> ' lines under '### CODE ...' in docs/attack-pieces.md or
docs/concept-prompts.md), sends it to ComfyUI running on this PC (C:\\Users\\thecl\\ComfyUI, started for you if it
isn't running) with the Qwen-Image model, and saves the takes to docs/refs/gen/CODE-1.png, CODE-2.png... (ignored by
git: copy the one you pick to docs/refs/pk-code.png as usual). Runs on the graphics card; nothing goes online.
"""
import argparse, json, os, random, re, subprocess, sys, time, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMFY = r'C:\Users\thecl\ComfyUI'
URL = 'http://127.0.0.1:8188'
OUT = os.path.join(ROOT, 'Art', 'Refs', 'gen')
DOCS = [os.path.join(ROOT, 'docs', 'prompts.md')]   # '### CODE' headings with '> ' prompt lines
NEG = 'blurry, lens flare, text, letters, numbers, watermark, signature, logo, frame, border, panels, grid lines'


def find_prompt(code):
    for path in DOCS:
        if not os.path.exists(path): continue
        lines = open(path, encoding='utf-8').read().split('\n')
        for i, l in enumerate(lines):
            if re.match(r'#{2,4} ' + re.escape(code) + r'\b', l):
                out = []
                for l2 in lines[i + 1:]:
                    if l2.startswith('#'): break
                    if l2.startswith('> '): out.append(l2[2:].strip())
                    elif out and not l2.strip(): break
                if out: return ' '.join(out)
    return None


def api(path, data=None):
    req = urllib.request.Request(URL + path, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r: return r.read()


def running():
    try: api('/system_stats'); return True
    except Exception: return False


def start_comfy():
    if running(): return
    print('starting ComfyUI...')
    py = os.path.join(COMFY, 'venv', 'Scripts', 'python.exe')
    log = open(os.path.join(COMFY, 'comfy.log'), 'a')
    subprocess.Popen([py, 'main.py', '--listen', '127.0.0.1', '--port', '8188'], cwd=COMFY, stdout=log, stderr=log,
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    for _ in range(180):
        time.sleep(2)
        if running(): print('ComfyUI is up'); return
    sys.exit('ComfyUI did not start: see ' + os.path.join(COMFY, 'comfy.log'))


def upload(path):
    # send a reference picture to ComfyUI's input folder; returns the name it's stored under
    name, b, nl = os.path.basename(path), '----deeparchive', chr(13) + chr(10)
    head = nl.join(['--' + b, f'Content-Disposition: form-data; name="image"; filename="{name}"', 'Content-Type: image/png', '', ''])
    tail = nl.join(['', '--' + b, 'Content-Disposition: form-data; name="overwrite"', '', 'true', '--' + b + '--', ''])
    body = head.encode() + open(path, 'rb').read() + tail.encode()
    req = urllib.request.Request(URL + '/upload/image', data=body, headers={'Content-Type': 'multipart/form-data; boundary=' + b})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())['name']


def edit_workflow(prompt, seed, w, h, steps, neg, cfg, refs, model):
    # Qwen-Image-Edit: the reference pictures (our Gemini sheets) go in with the prompt, so it draws in their style
    wf = {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': model, 'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'type': 'qwen_image'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'qwen_image_vae.safetensors'}},
        '4': {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'model': ['1', 0], 'shift': 3.1}},
        '12': {'class_type': 'CFGNorm', 'inputs': {'model': ['4', 0], 'strength': 1.0}},
        '7': {'class_type': 'EmptySD3LatentImage', 'inputs': {'width': w, 'height': h, 'batch_size': 1}},
        '9': {'class_type': 'VAEDecode', 'inputs': {'samples': ['8', 0], 'vae': ['3', 0]}},
        '10': {'class_type': 'SaveImage', 'inputs': {'images': ['9', 0], 'filename_prefix': 'megajam'}},
    }
    imgs = {}
    for i, r in enumerate(refs[:3]):
        wf[f'r{i}'] = {'class_type': 'LoadImage', 'inputs': {'image': r}}
        wf[f's{i}'] = {'class_type': 'ImageScaleToTotalPixels', 'inputs': {'image': [f'r{i}', 0], 'upscale_method': 'nearest-exact', 'megapixels': 1.0, 'resolution_steps': 1}}
        imgs[f'image{i + 1}'] = [f's{i}', 0]
    for k, text in (('5', prompt), ('6', NEG + (', ' + neg if neg else ''))):
        wf['t' + k] = {'class_type': 'TextEncodeQwenImageEditPlus', 'inputs': {'clip': ['2', 0], 'vae': ['3', 0], 'prompt': text, **imgs}}
        wf[k] = {'class_type': 'FluxKontextMultiReferenceLatentMethod', 'inputs': {'conditioning': ['t' + k, 0], 'reference_latents_method': 'index_timestep_zero'}}
    wf['8'] = {'class_type': 'KSampler', 'inputs': {'model': ['12', 0], 'positive': ['5', 0], 'negative': ['6', 0], 'latent_image': ['7', 0],
               'seed': seed, 'steps': steps, 'cfg': cfg, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}}
    return wf


def workflow(prompt, seed, w, h, steps, neg='', cfg=2.5, model='qwen_image_2512_fp8_e4m3fn.safetensors', lora=None, lora_k=1.0, refs=None):
    if refs: return edit_workflow(prompt, seed, w, h, steps, neg, cfg, refs, model)
    wf = {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': model, 'weight_dtype': 'fp8_e4m3fn'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'type': 'qwen_image'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'qwen_image_vae.safetensors'}},
        '4': {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'model': ['1', 0], 'shift': 3.1}},
        '5': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': prompt}},
        '6': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': NEG + (', ' + neg if neg else '')}},
        '7': {'class_type': 'EmptySD3LatentImage', 'inputs': {'width': w, 'height': h, 'batch_size': 1}},
        '8': {'class_type': 'KSampler', 'inputs': {'model': ['4', 0], 'positive': ['5', 0], 'negative': ['6', 0], 'latent_image': ['7', 0],
              'seed': seed, 'steps': steps, 'cfg': cfg, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}},
        '9': {'class_type': 'VAEDecode', 'inputs': {'samples': ['8', 0], 'vae': ['3', 0]}},
        '10': {'class_type': 'SaveImage', 'inputs': {'images': ['9', 0], 'filename_prefix': 'deeparchive'}},
    }
    if lora:   # an add-on trained for a look (the pixel-art LoRA), between the model and the sampler
        wf['11'] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {'model': ['1', 0], 'lora_name': lora, 'strength_model': lora_k}}
        wf['4']['inputs']['model'] = ['11', 0]
    return wf


def generate(prompt, name, seed, w, h, steps, neg='', cfg=2.5, **kw):
    pid = json.loads(api('/prompt', {'prompt': workflow(prompt, seed, w, h, steps, neg, cfg, **kw)}))['prompt_id']
    t0 = time.time()
    while True:
        time.sleep(1.5)
        hist = json.loads(api('/history/' + pid))
        if pid in hist:
            outs = hist[pid].get('outputs', {})
            if not outs: sys.exit('ComfyUI reported no output: ' + json.dumps(hist[pid].get('status', {}))[:400])
            img = next(iter(outs.values()))['images'][0]
            q = urllib.parse.urlencode({'filename': img['filename'], 'subfolder': img['subfolder'], 'type': img['type']})
            data = urllib.request.urlopen(URL + '/view?' + q, timeout=60).read()
            os.makedirs(OUT, exist_ok=True)
            path = os.path.join(OUT, name + '.png'); open(path, 'wb').write(data)
            print(f'  {name}.png  ({time.time() - t0:.0f} s)')
            return path
        if time.time() - t0 > 900: sys.exit('timed out waiting for ' + name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('codes', nargs='*')
    ap.add_argument('--text'); ap.add_argument('--neg', default=''); ap.add_argument('--cfg', type=float, default=4); ap.add_argument('--name'); ap.add_argument('--model', default='qwen_image_2512_fp8_e4m3fn.safetensors'); ap.add_argument('--lora', default=None); ap.add_argument('--lora-k', type=float, default=0.8); ap.add_argument('--takes', type=int, default=2); ap.add_argument('--seed', type=int)
    ap.add_argument('--ref', action='append', default=[], help='a style reference picture (up to 3); switches to the edit model'); ap.add_argument('--size', default='1664x928'); ap.add_argument('--steps', type=int, default=30)
    a = ap.parse_args()
    w, h = map(int, a.size.split('x'))
    jobs = [(a.name or 'custom-' + str(int(time.time())), a.text)] if a.text else [(c, find_prompt(c)) for c in a.codes]
    for c, p in jobs:
        if not p: sys.exit(f'no prompt found for {c} (looked for "### {c}" in the prompt docs)')
    start_comfy()
    refs = [upload(r) for r in a.ref]
    if refs:   # the edit model draws from the references; the pixel-art add-on is for the other model
        a.lora = None
        if a.model.startswith('qwen_image_2512'): a.model = 'qwen_image_edit_2511_fp8mixed.safetensors'
    seed = a.seed if a.seed is not None else random.randrange(1 << 30)
    for code, prompt in jobs:
        if a.lora and not prompt.startswith('Pixel Art'): prompt = 'Pixel Art, ' + prompt   # the add-on's trigger words
        print(code)
        for k in range(a.takes): generate(prompt, f'{code}-{k + 1}', seed + k, w, h, a.steps, a.neg, a.cfg, model=a.model, lora=a.lora, lora_k=a.lora_k, refs=refs)


if __name__ == '__main__':
    main()
