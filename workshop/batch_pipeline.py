"""
Autonomous AIGC Batch Pipeline
Runs after SDXL LoRA training completes:
1. Wait for training to finish
2. Test all saved checkpoints
3. Batch generate pose/prompt variants
4. Save results to organized directories
"""
import sys, os, json, time, subprocess, shutil, glob, re
from pathlib import Path

# ====== CONFIG ======
LORA_DIR = r'C:\DrawingLive\ComfyUI\models\loras'
OUTPUT_DIR = r'C:\DrawingLive\ComfyUI\output'
COMFY_API = 'http://127.0.0.1:8188/prompt'
CKPT = r'waiIllustriousSDXL_v160.safetensors'
PYTHON = r'C:\DrawingLive\ComfyUI\venv\Scripts\python.exe'
TRAIN_LOG = r'C:\Users\zwq\kohya_ss\sd-scripts\train_progress.log'

RESULTS_DIR = r'C:\Users\zwq\aigc-comfy-pipeline\workshop\batch_output'
os.makedirs(RESULTS_DIR, exist_ok=True)

NEGATIVE = 'low quality, bad anatomy, bad hands, extra fingers, missing fingers, deformed face, wrong hair color, short hair, modern clothes, realistic, 3d render'

# ====== PROMPT VARIANTS ======
BASE_PROMPT = (
    "1girl, shm_character, half black half white hair, long flowing hair, "
    "pinkish violet eyes, lavender iris, small dark pupils, gold hair ornament, "
    "black ribbon, pale skin, small oval face, delicate face, anime style, "
    "fantasy girl, navy blue and white costume, gold embroidery, royal uniform, "
    "{extra}, full body, high quality, detailed illustration, masterpiece"
)

VARIANTS = [
    # pose variants
    "natural standing pose, looking at viewer, calm expression",
    "standing pose, looking away, soft smile, wind blowing hair",
    "walking pose, dynamic, flowing cape",
    "one hand raised, gentle smile, casting magic",
    "sitting pose, elegant, hands together, serene expression",
    "turning around, looking back, hair flowing",
    # environment variants  
    "standing in fantasy forest, magical atmosphere, glowing lights",
    "standing in moonlight, cathedral background, ethereal atmosphere",
    "on castle balcony, night sky, stars, elegant pose",
    "magical circle background, casting spell, glowing orb",
    # expression variants
    "serious expression, confident gaze, powerful stance",
    "surprised expression, wide eyes, dynamic pose",
    "gentle smile, warm expression, approachable",
    "emotionless face, cold gaze, mysterious atmosphere",
]

# ====== HELPERS ======
def comfy_queue(workflow):
    data = json.dumps({'prompt': workflow, 'client_id': 'batch_runner'}).encode()
    import urllib.request
    req = urllib.request.Request(COMFY_API, data=data,
        headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())

def wait_comfy():
    """Wait until ComfyUI queue is empty"""
    import urllib.request
    while True:
        try:
            resp = urllib.request.urlopen('http://127.0.0.1:8188/queue', timeout=5)
            q = json.loads(resp.read())
            running = len(q.get('queue_running', []))
            pending = len(q.get('queue_pending', []))
            if running == 0 and pending == 0:
                return
            time.sleep(3)
        except:
            time.sleep(5)

def build_workflow(lora_name, lora_strength, prompt_text, seed=42, 
                   width=768, height=768):
    """Build ComfyUI workflow with LoRA"""
    return {
        '3': {'class_type': 'CheckpointLoaderSimple',
              'inputs': {'ckpt_name': CKPT}},
        '10': {'class_type': 'LoraLoader',
               'inputs': {'model': ['3', 0], 'clip': ['3', 1],
                 'lora_name': lora_name,
                 'strength_model': lora_strength,
                 'strength_clip': lora_strength}},
        '4': {'class_type': 'CLIPTextEncode',
              'inputs': {'text': prompt_text, 'clip': ['10', 1]}},
        '5': {'class_type': 'CLIPTextEncode',
              'inputs': {'text': NEGATIVE, 'clip': ['10', 1]}},
        '6': {'class_type': 'EmptyLatentImage',
              'inputs': {'width': width, 'height': height, 'batch_size': 1}},
        '7': {'class_type': 'KSampler',
              'inputs': {'seed': seed, 'steps': 28, 'cfg': 7,
                'sampler_name': 'euler', 'scheduler': 'normal', 'denoise': 1,
                'model': ['10', 0], 'positive': ['4', 0],
                'negative': ['5', 0], 'latent_image': ['6', 0]}},
        '8': {'class_type': 'VAEDecode',
              'inputs': {'samples': ['7', 0], 'vae': ['3', 2]}},
        '9': {'class_type': 'SaveImage',
              'inputs': {'filename_prefix': 'batch_v2', 'images': ['8', 0]}},
    }

# ====== PHASE 1: Wait for training ======
print('='*60)
print('PHASE 1: Monitoring LoRA training...')
print('='*60)

lora_files = []
while True:
    files = sorted(glob.glob(os.path.join(LORA_DIR, 'my_char_v2-*.safetensors')))
    if files and not any('tmp' in f for f in files):
        # Check if process is still running (training pid)
        # We just check if files keep changing
        latest = max(files, key=os.path.getmtime)
        age = time.time() - os.path.getmtime(latest)
        if age > 120 and len(files) >= 3:
            # No new file for 2 min and at least 3 saves = probably done
            print(f'Training appears complete. Latest: {os.path.basename(latest)}')
            lora_files = files
            break
    
    # Check if a recent file has been modified (training active)
    if files:
        latest = max(files, key=os.path.getmtime)
        mtime = os.path.getmtime(latest)
        age = time.time() - mtime
        print(f'  Training in progress... {len(files)} checkpoints, last: {os.path.basename(latest)} ({age:.0f}s ago)')
    
    time.sleep(60)

time.sleep(30)  # Grace period

# Re-scan all checkpoints
lora_files = sorted(glob.glob(os.path.join(LORA_DIR, 'my_char_v2-*.safetensors')))
print(f'Found {len(lora_files)} checkpoints')

# ====== PHASE 2: Quick test all checkpoints ======
print()
print('='*60)
print('PHASE 2: Testing checkpoints...')
print('='*60)

test_prompt = BASE_PROMPT.format(extra='natural standing pose, looking at viewer, calm expression')

# Group checkpoints by batch (test first, middle, last)
selected = []
if len(lora_files) >= 3:
    selected = [lora_files[0], lora_files[len(lora_files)//3], 
                lora_files[2*len(lora_files)//3], lora_files[-1]]
elif len(lora_files) > 0:
    selected = [lora_files[-1]]

test_results = {}
for ckpt_path in selected:
    ckpt_name = os.path.basename(ckpt_path)
    print(f'Testing {ckpt_name}...')
    
    for strength in [0.6, 0.8, 1.0]:
        wf = build_workflow(ckpt_name, strength, test_prompt, 
                           seed=42 + int(strength * 10))
        try:
            result = comfy_queue(wf)
            print(f'  str={strength}: queued OK')
        except Exception as e:
            print(f'  str={strength}: QUEUE FAILED - {e}')
        
        wait_comfy()

print('Testing complete.')

# ====== PHASE 3: Batch generation ======
print()
print('='*60)
print('PHASE 3: Batch generation with best checkpoint...')
print('='*60)

# Use last checkpoint with best strength
best_lora = os.path.basename(lora_files[-1]) if lora_files else 'my_char_v2.safetensors'
best_strength = 0.8

for i, variant in enumerate(VARIANTS):
    prompt = BASE_PROMPT.format(extra=variant)
    print(f'  [{i+1}/{len(VARIANTS)}] {variant[:50]}...')
    
    for seed_offset in range(3):  # 3 seeds per variant
        wf = build_workflow(best_lora, best_strength, prompt,
                          seed=100 + i * 10 + seed_offset)
        try:
            comfy_queue(wf)
        except Exception as e:
            print(f'    seed+{seed_offset}: FAILED - {e}')
    
    wait_comfy()

# ====== PHASE 4: Copy results ======
print()
print('='*60)
print('PHASE 4: Organizing results...')
print('='*60)

output_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, 'batch_v2_*.png')))
print(f'Generated {len(output_files)} images')

# Copy to results directory
for f in output_files:
    shutil.copy2(f, RESULTS_DIR)

# Save metadata
meta = {
    'lora': best_lora,
    'strength': best_strength,
    'checkpoint': CKPT,
    'variants': len(VARIANTS),
    'images': len(output_files),
    'prompt': BASE_PROMPT,
    'negative': NEGATIVE,
    'total_time': time.strftime('%H:%M:%S'),
}
with open(os.path.join(RESULTS_DIR, 'batch_metadata.json'), 'w') as f:
    json.dump(meta, f, indent=2)

print(f'Results saved to: {RESULTS_DIR}')
print()
print('='*60)
print('BATCH PIPELINE COMPLETE')
print(f'Total images: {len(output_files)}')
print(f'Best LoRA: {best_lora}')
print('='*60)
