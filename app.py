"""Local video transcription: Tk frontend, isolated GPU worker, atomic outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback

FROZEN = bool(getattr(sys, 'frozen', False))
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', APP_DIR))
PORTABLE = FROZEN or (APP_DIR / 'portable.json').is_file()
ROOT = APP_DIR
MEDIA = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.m4v', '.wmv', '.flv',
         '.ts', '.mts', '.m2ts', '.mpg', '.mpeg', '.mp3', '.wav', '.m4a',
         '.aac', '.flac', '.ogg', '.opus', '.wma'}
LANGUAGES = {'自动识别': None, '日语': 'ja', '中文': 'zh', '英语': 'en',
             '韩语': 'ko', '德语': 'de', '法语': 'fr'}
DLL_HANDLES = []
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def prepare_runtime():
    os.environ['HF_HOME'] = str(ROOT / 'models')
    os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
    # Private DLL lookup: never change system PATH or existing AI environments.
    nvidia = (RESOURCE_DIR / 'nvidia' if FROZEN else
              Path(sys.prefix) / 'Lib' / 'site-packages' / 'nvidia')
    if os.name == 'nt' and nvidia.is_dir():
        folders = sorted({p.parent for p in nvidia.rglob('*.dll')})
        for folder in folders:
            DLL_HANDLES.append(os.add_dll_directory(str(folder)))
        os.environ['PATH'] = os.pathsep.join(map(str, folders)) + os.pathsep + os.environ.get('PATH', '')


def ffmpeg_path():
    bundled = RESOURCE_DIR / 'ffmpeg' / 'ffmpeg.exe'
    if bundled.is_file():
        return str(bundled)
    bundled = APP_DIR / '_internal' / 'ffmpeg' / 'ffmpeg.exe'
    return str(bundled) if bundled.is_file() else shutil.which('ffmpeg')


def worker_command(job_path, events_path):
    if FROZEN:
        return [sys.executable, '--worker', str(job_path), '--events', str(events_path)]
    executable = Path(sys.executable).with_name('python.exe') if os.name == 'nt' else Path(sys.executable)
    return [str(executable), '-u', str(APP_DIR / 'app.py'), '--worker', str(job_path),
            '--events', str(events_path)]


def initialize_data_root():
    global ROOT
    if not PORTABLE:
        return
    ROOT = APP_DIR / 'data'
    try:
        ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryFile(dir=ROOT):
            pass
    except OSError:
        ROOT = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'VideoTranscriber'
        ROOT.mkdir(parents=True, exist_ok=True)


def load_model(name, device=None):
    import ctranslate2
    from faster_whisper import WhisperModel
    from faster_whisper.utils import download_model
    from huggingface_hub.errors import LocalEntryNotFoundError
    bundled = APP_DIR / 'models' / name
    if (bundled / 'model.bin').is_file():
        model_path = str(bundled)
    else:
        cache = str(ROOT / 'models' / 'whisper')
        try:
            model_path = download_model(name, cache_dir=cache, local_files_only=True)
        except LocalEntryNotFoundError:
            model_path = download_model(name, cache_dir=cache)
    device = device or ('cuda' if ctranslate2.get_cuda_device_count() else 'cpu')
    return WhisperModel(model_path, device=device,
                        compute_type='float16' if device == 'cuda' else 'int8')


def emit(kind, **fields):
    print(json.dumps({'event': kind, **fields}, ensure_ascii=False), flush=True)


def atomic_write(path, text):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(text, encoding='utf-8')
    os.replace(temp, path)


def timestamp(seconds):
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    seconds, millis = divmod(millis, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{millis:03}'


def collect_media(folder, recursive=True):
    root = Path(folder)
    entries = root.rglob('*') if recursive else root.iterdir()
    return sorted(p for p in entries if p.is_file() and p.suffix.lower() in MEDIA)


def source_signature(source, job):
    stat = source.stat()
    return {'path': str(source.resolve()), 'size': stat.st_size,
            'mtime_ns': stat.st_mtime_ns, 'model': job['model'],
            'language': job['language'], 'pipeline': 1}


def output_paths(source, job):
    digest = hashlib.sha256(str(source.resolve()).casefold().encode()).hexdigest()[:10]
    folder = Path(job['output']) / (job['model'] + '_' + (job['language'] or 'auto'))
    base = folder / f'{source.stem[:70]}_{digest}'
    return {extension: Path(str(base) + '.' + extension) for extension in ('txt', 'srt', 'json')}


def already_done(paths, signature):
    try:
        return (all(p.is_file() for p in paths.values()) and
                json.loads(paths['json'].read_text(encoding='utf-8'))['signature'] == signature)
    except (OSError, ValueError, KeyError):
        return False


class Cancelled(Exception):
    pass


def check_cancel(job):
    if Path(job['cancel']).exists():
        raise Cancelled()


def extract_audio(source, target, job):
    check_cancel(job)
    command = [ffmpeg_path(), '-nostdin', '-hide_banner', '-loglevel', 'error',
               '-y', '-i', str(source), '-map', '0:a:0', '-vn', '-ac', '1',
               '-ar', '16000', '-c:a', 'pcm_s16le', str(target)]
    # File-backed stderr prevents pipe deadlock on a corrupt input.
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=errors,
                                creationflags=NO_WINDOW)
        try:
            while proc.poll() is None:
                check_cancel(job)
                time.sleep(.15)
            if proc.returncode:
                errors.seek(0)
                detail = errors.read().decode('utf-8', errors='replace')[-3000:]
                raise RuntimeError('无法读取音轨（视频需要包含音频）：' + detail)
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait()


def run_worker(job):
    prepare_runtime()
    if not ffmpeg_path():
        raise RuntimeError('找不到 FFmpeg。便携版请完整解压后运行，不要只复制 EXE。')
    import ctranslate2
    from faster_whisper import BatchedInferencePipeline
    device = job.get('device') or ('cuda' if ctranslate2.get_cuda_device_count() else 'cpu')
    if device == 'cpu':
        emit('status', text='使用 CPU 兼容模式，处理速度会比 NVIDIA 显卡慢。')
    failures = completed = skipped = 0
    pipeline = None
    started = time.perf_counter()
    for index, name in enumerate(job['files']):
        source = Path(name)
        try:
            check_cancel(job)
            signature = source_signature(source, job)
            paths = output_paths(source, job)
            if job['skip'] and already_done(paths, signature):
                skipped += 1
                emit('file', index=index, state='已跳过', detail='已有完整结果')
                continue
            if pipeline is None:
                emit('status', text='正在加载本地模型…' if (APP_DIR / 'models' / job['model']).is_dir()
                     else '正在加载模型；未缓存的模型会自动下载…')
                model = load_model(job['model'], device)
                pipeline = BatchedInferencePipeline(model=model)
                check_cancel(job)
            item_start = time.perf_counter()
            emit('file', index=index, state='提取音轨', detail='自动处理，无需手动转换')
            with tempfile.TemporaryDirectory(prefix='audio-', dir=ROOT / 'cache') as temp:
                audio = Path(temp) / 'audio.wav'
                extract_audio(source, audio, job)
                import wave
                import numpy as np
                with wave.open(str(audio)) as wav:
                    duration = wav.getnframes() / wav.getframerate()
                    # FFmpeg already normalized to 16 kHz mono PCM16. Passing the
                    # samples avoids a redundant decode and PyAV API drift.
                    samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32)
                    samples /= 32768.0
                emit('file', index=index, state='转写中', detail=f'音频 {duration / 60:.1f} 分钟')
                segments, info = pipeline.transcribe(
                    samples, language=job['language'], task='transcribe',
                    batch_size=job['batch'], beam_size=5, vad_filter=True,
                    word_timestamps=False)
                rows = []
                last_update = 0
                for seg in segments:
                    check_cancel(job)
                    rows.append({'start': seg.start, 'end': seg.end, 'text': seg.text.strip()})
                    now = time.perf_counter()
                    if now - last_update > .5:
                        elapsed = now - item_start
                        emit('progress', index=index, seconds=seg.end, duration=duration,
                             elapsed=elapsed, speed=seg.end / max(elapsed, .01))
                        last_update = now
                check_cancel(job)
                paths['txt'].parent.mkdir(parents=True, exist_ok=True)
                atomic_write(paths['txt'], '\n\n'.join(r['text'] for r in rows) + '\n')
                subtitles = '\n\n'.join(
                    f"{i}\n{timestamp(r['start'])} --> {timestamp(r['end'])}\n{r['text']}"
                    for i, r in enumerate(rows, 1))
                atomic_write(paths['srt'], subtitles + '\n')
                elapsed = time.perf_counter() - item_start
                # Completion manifest written last, so interrupted output is never skipped.
                atomic_write(paths['json'], json.dumps({
                    'signature': signature, 'language_detected': info.language,
                    'duration': duration, 'elapsed': elapsed, 'batch_size': job['batch'],
                    'segments': rows}, ensure_ascii=False, indent=2))
                completed += 1
                emit('file', index=index, state='已完成',
                     detail=f'{elapsed:.1f} 秒 · {duration / max(elapsed, .01):.1f} 倍速',
                     output=str(paths['txt']))
        except Cancelled:
            emit('file', index=index, state='已停止', detail='完整结果已保留，可以再次开始')
            emit('cancelled')
            return 2
        except Exception as exc:
            failures += 1
            emit('file', index=index, state='失败', detail=str(exc))
            traceback.print_exc(file=sys.stderr)
            # A failed model load will affect every file: stop with a clear global error.
            if pipeline is None:
                raise
    emit('finished', completed=completed, skipped=skipped, failed=failures,
         elapsed=time.perf_counter() - started)
    return 1 if failures else 0


def show_gui(initial_paths=(), smoke_job=None):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    class App:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title('视频转文字 · 本地 GPU 批量转写')
            icon = RESOURCE_DIR / 'app.ico'
            if icon.is_file():
                self.root.iconbitmap(str(icon))
            self.root.geometry('1050x760')
            self.root.minsize(900, 640)
            self.root.option_add('*Font', ('Microsoft YaHei UI', 10))
            style = ttk.Style(self.root)
            style.theme_use('clam')
            style.configure('Treeview', rowheight=26)
            style.configure('Title.TLabel', font=('Microsoft YaHei UI', 19, 'bold'))
            style.configure('Go.TButton', font=('Microsoft YaHei UI', 11, 'bold'), padding=(20, 10))
            self.files = []
            self.events = queue.Queue()
            self.process = None
            self.run_started = 0
            self.cancel_file = None
            self.job_path = None
            self.finished_event = False
            self.output = tk.StringVar(value=str(ROOT / 'results'))
            self.language = tk.StringVar(value='自动识别')
            self.model = tk.StringVar(value='turbo')
            self.batch = tk.StringVar(value='16')
            self.recursive = tk.BooleanVar(value=True)
            self.skip = tk.BooleanVar(value=True)
            self.status = tk.StringVar(value='添加视频或文件夹，然后点击“开始转写”。')
            frame = ttk.Frame(self.root, padding=16)
            frame.pack(fill='both', expand=True)
            ttk.Label(frame, text='视频转文字', style='Title.TLabel').pack(anchor='w')
            ttk.Label(frame, text='选择视频 → 自动提取音轨 → GPU 转写 → 导出 TXT / SRT',
                      foreground='#576574').pack(anchor='w', pady=(4, 10))
            toolbar = ttk.Frame(frame)
            toolbar.pack(fill='x', pady=(0, 10))
            self.edit_controls = []
            for label, callback in [('添加视频 / 音频', self.add_files), ('添加文件夹', self.add_folder),
                                     ('移除选中', self.remove), ('清空列表', self.clear)]:
                button = ttk.Button(toolbar, text=label, command=callback)
                button.pack(side='left', padx=(0, 8))
                self.edit_controls.append(button)
            recursive = ttk.Checkbutton(toolbar, text='包含子文件夹', variable=self.recursive)
            recursive.pack(side='left', padx=8)
            self.edit_controls.append(recursive)
            table = ttk.Frame(frame)
            table.pack(fill='both', expand=True)
            self.tree = ttk.Treeview(table, columns=('name', 'state', 'detail'), show='headings', height=5)
            for key, label, width in [('name', '视频 / 音频文件', 350), ('state', '状态', 95),
                                      ('detail', '进度 / 结果', 420)]:
                self.tree.heading(key, text=label)
                self.tree.column(key, width=width, minwidth=70)
            scrollbar = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
            self.tree.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side='right', fill='y')
            self.tree.pack(fill='both', expand=True)
            settings = ttk.LabelFrame(frame, text='转写设置', padding=10)
            settings.pack(fill='x', pady=8)
            for column, (label, variable, values) in enumerate([
                ('音频语言', self.language, list(LANGUAGES)),
                ('模型', self.model, ['turbo', 'large-v3']),
                ('批量大小', self.batch, ['4', '8', '16', '32'])]):
                ttk.Label(settings, text=label).grid(row=0, column=column * 2, padx=(0, 8))
                combo = ttk.Combobox(settings, textvariable=variable, values=values,
                                     state='readonly', width=12)
                combo.grid(row=0, column=column * 2 + 1, padx=(0, 20))
                self.edit_controls.append(combo)
            ttk.Label(settings, text='turbo：速度优先    large-v3：适合对照检查准确率',
                      foreground='#576574').grid(row=1, column=0, columnspan=6, sticky='w', pady=(10, 0))
            pathrow = ttk.Frame(frame)
            pathrow.pack(fill='x')
            ttk.Label(pathrow, text='结果目录').pack(side='left', padx=(0, 10))
            output_entry = ttk.Entry(pathrow, textvariable=self.output)
            output_entry.pack(side='left', fill='x', expand=True)
            choose = ttk.Button(pathrow, text='选择…', command=self.choose_output)
            choose.pack(side='left', padx=(8, 0))
            ttk.Button(pathrow, text='打开结果', command=self.open_output).pack(side='left', padx=(8, 0))
            self.edit_controls.extend([output_entry, choose])
            skip_button = ttk.Checkbutton(frame, text='跳过已完成文件（校验来源文件、模型、语言和完整结果）', variable=self.skip)
            skip_button.pack(anchor='w', pady=(10, 8))
            self.edit_controls.append(skip_button)
            self.progress = ttk.Progressbar(frame, maximum=100)
            self.progress.pack(fill='x', pady=(4, 8))
            ttk.Label(frame, textvariable=self.status, wraplength=970).pack(anchor='w')
            actions = ttk.Frame(frame)
            actions.pack(fill='x', pady=(8, 6))
            self.start_button = ttk.Button(actions, text='开始转写', style='Go.TButton', command=self.start)
            self.start_button.pack(side='left')
            self.stop_button = ttk.Button(actions, text='停止', command=self.stop, state='disabled')
            self.stop_button.pack(side='left', padx=12)
            self.elapsed_label = ttk.Label(actions, text='')
            self.elapsed_label.pack(side='right')
            self.log = tk.Text(frame, height=3, wrap='word', font=('Microsoft YaHei UI', 9), state='disabled')
            self.log.pack(fill='x')
            ttk.Label(frame, text=('已内置 turbo 模型。视频在本机处理；临时音轨自动清理。' if PORTABLE else
                                  '首次使用会下载模型。视频留在本机；临时音轨处理后自动清理。'),
                      foreground='#576574').pack(anchor='w', pady=(8, 0))
            self.root.protocol('WM_DELETE_WINDOW', self.close)
            self.root.after(150, self.poll)

        def add(self, paths):
            seen = {str(p).casefold() for p in self.files}
            for path in paths:
                path = Path(path).resolve()
                if path.suffix.lower() in MEDIA and str(path).casefold() not in seen:
                    self.files.append(path)
                    seen.add(str(path).casefold())
                    self.tree.insert('', 'end', values=(path.name, '等待', str(path.parent)))
            self.status.set(f'队列共 {len(self.files)} 个文件。')

        def add_files(self):
            self.add(filedialog.askopenfilenames(title='选择视频或音频', filetypes=[
                ('视频 / 音频', ' '.join('*' + ext for ext in sorted(MEDIA))), ('所有文件', '*.*')]))

        def add_folder(self):
            folder = filedialog.askdirectory(title='选择视频文件夹')
            if folder:
                try:
                    self.add(collect_media(folder, self.recursive.get()))
                except OSError as exc:
                    messagebox.showerror('无法扫描文件夹', str(exc))

        def remove(self):
            children = list(self.tree.get_children())
            selected = set(self.tree.selection())
            self.files = [p for item, p in zip(children, self.files) if item not in selected]
            for item in selected:
                self.tree.delete(item)
            self.status.set(f'队列共 {len(self.files)} 个文件。')

        def clear(self):
            self.tree.delete(*self.tree.get_children())
            self.files.clear()
            self.status.set('队列已清空。')

        def choose_output(self):
            folder = filedialog.askdirectory(title='选择结果保存位置')
            if folder:
                self.output.set(folder)

        def open_output(self):
            try:
                folder = Path(self.output.get()).expanduser().resolve()
                folder.mkdir(parents=True, exist_ok=True)
                os.startfile(folder)
            except OSError as exc:
                messagebox.showerror('无法打开目录', str(exc))

        def append_log(self, text):
            self.log.configure(state='normal')
            self.log.insert('end', text + '\n')
            self.log.see('end')
            self.log.configure(state='disabled')

        def busy(self, active):
            for widget in self.edit_controls:
                widget.configure(state='disabled' if active else
                                 ('readonly' if isinstance(widget, ttk.Combobox) else 'normal'))
            self.start_button.configure(state='disabled' if active else 'normal')
            self.stop_button.configure(state='normal' if active else 'disabled')

        def start(self):
            if not self.files:
                messagebox.showinfo('先添加视频', '可以选择多个视频，或者添加整个文件夹。')
                return
            if not self.output.get().strip():
                messagebox.showerror('请选择结果目录', '结果目录不能为空。')
                return
            try:
                output = Path(self.output.get()).expanduser().resolve()
                output.mkdir(parents=True, exist_ok=True)
                cache = ROOT / 'cache'
                cache.mkdir(exist_ok=True)
                run_id = str(time.time_ns())
                self.cancel_file = cache / (run_id + '.stop')
                self.job_path = cache / (run_id + '.job.json')
                job = {'files': list(map(str, self.files)), 'output': str(output),
                       'language': LANGUAGES[self.language.get()], 'model': self.model.get(),
                       'batch': int(self.batch.get()), 'skip': self.skip.get(),
                       'cancel': str(self.cancel_file)}
                atomic_write(self.job_path, json.dumps(job, ensure_ascii=False))
                log_path = ROOT / 'logs' / (run_id + '.log')
                log_path.parent.mkdir(exist_ok=True)
                log_path.touch()
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                self.process = subprocess.Popen(worker_command(self.job_path, log_path),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env=env, creationflags=NO_WINDOW)
            except Exception as exc:
                messagebox.showerror('启动失败', str(exc))
                return
            self.run_started = time.perf_counter()
            self.finished_event = False
            self.progress['value'] = 0
            self.busy(True)
            self.status.set('正在启动 GPU 转写引擎…')
            for item in self.tree.get_children():
                self.tree.set(item, 'state', '等待')
            worker = self.process

            def reader():
                pending = ''
                with log_path.open('r', encoding='utf-8', errors='replace') as stream:
                    while True:
                        pending += stream.read()
                        lines = pending.split('\n')
                        pending = lines.pop()
                        for line in lines:
                            self.queue_line(line)
                        if worker.poll() is not None:
                            pending += stream.read()
                            if pending:
                                for line in pending.splitlines():
                                    self.queue_line(line)
                            break
                        time.sleep(.15)
                worker.wait()
                self.events.put({'event': 'exit', 'code': worker.returncode})
            threading.Thread(target=reader, daemon=True).start()

        def queue_line(self, line):
            try:
                event = json.loads(line)
                if not isinstance(event, dict) or 'event' not in event:
                    raise ValueError()
            except ValueError:
                event = {'event': 'log', 'text': line.strip()}
            self.events.put(event)

        def stop(self):
            if self.process and self.cancel_file:
                self.cancel_file.touch()
                self.status.set('正在停止；模型下载 / 当前计算片段结束后退出，已完成结果会保留。')
                self.stop_button.configure(state='disabled')

        def poll(self):
            while not self.events.empty():
                event = self.events.get()
                kind = event['event']
                children = self.tree.get_children()
                index = event.get('index', 0)
                if kind == 'file':
                    self.tree.set(children[index], 'state', event['state'])
                    self.tree.set(children[index], 'detail', event['detail'])
                    self.tree.see(children[index])
                    self.status.set(f"{index + 1}/{len(self.files)} · {self.files[index].name} · {event['state']}")
                    if event['state'] in ('已完成', '已跳过', '失败'):
                        self.progress['value'] = (index + 1) / len(self.files) * 100
                    self.append_log(f"{self.files[index].name}：{event['state']} · {event['detail']}")
                elif kind == 'progress':
                    fraction = min(event['seconds'] / max(event['duration'], .01), 1)
                    self.progress['value'] = (index + fraction) / len(self.files) * 100
                    self.tree.set(children[index], 'detail',
                                  f"{fraction:.0%} · 已用 {event['elapsed']:.0f} 秒 · {event['speed']:.1f} 倍速")
                elif kind == 'status':
                    self.status.set(event['text'])
                    self.append_log(event['text'])
                elif kind == 'log':
                    if event['text']:
                        self.append_log(event['text'])
                elif kind in ('finished', 'cancelled', 'fatal'):
                    self.finished_event = True
                    if kind == 'finished':
                        text = f"处理结束：完成 {event['completed']}，跳过 {event['skipped']}，失败 {event['failed']}。用时 {event['elapsed'] / 60:.1f} 分钟。"
                        self.progress['value'] = 100
                    elif kind == 'cancelled':
                        text = '已停止。已完成结果保留，再次开始会自动跳过。'
                    else:
                        text = '转写失败：' + event['text']
                    self.status.set(text)
                    self.append_log(text)
                elif kind == 'exit':
                    if not self.finished_event:
                        self.status.set(f"引擎异常退出（代码 {event['code']}）；请查看下方日志。显存不足时将批量大小降到 8 或 4。")
                    self.process = None
                    self.busy(False)
                    if self.job_path:
                        self.job_path.unlink(missing_ok=True)
                    if self.cancel_file:
                        self.cancel_file.unlink(missing_ok=True)
            if self.process:
                self.elapsed_label.configure(text=f'已用 {(time.perf_counter() - self.run_started) / 60:.1f} 分钟')
            self.root.after(150, self.poll)

        def close(self):
            if self.process:
                self.stop()
                messagebox.showinfo('正在停止', '请等待当前下载或计算片段结束，再关闭窗口。')
                return
            self.root.destroy()

    app = App()
    for path in initial_paths:
        path = Path(path)
        app.add(collect_media(path) if path.is_dir() else [path])
    if smoke_job:
        job = json.loads(Path(smoke_job).read_text(encoding='utf-8'))
        app.add(job['files'])
        app.output.set(job['output'])
        app.model.set(job['model'])
        app.language.set(next(k for k, v in LANGUAGES.items() if v == job['language']))
        app.batch.set(str(job['batch']))
        app.root.after(500, app.start)

        def finish_smoke():
            if app.run_started and app.process is None:
                atomic_write(Path(str(smoke_job) + '.gui-result.json'), json.dumps({
                    'status': app.status.get(), 'rows': [app.tree.item(item)['values']
                    for item in app.tree.get_children()]}, ensure_ascii=False, indent=2))
                app.root.destroy()
            else:
                app.root.after(200, finish_smoke)
        app.root.after(1000, finish_smoke)
    if '--smoke-ui' in sys.argv:
        app.root.after(500, app.root.destroy)
    app.root.mainloop()


def main():
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--events', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--smoke-job', type=Path)
    parser.add_argument('--download-model', choices=['turbo', 'large-v3'])
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--smoke-ui', action='store_true')
    parser.add_argument('files', nargs='*')
    args = parser.parse_args()
    if args.events or args.report:
        target = args.events or args.report
        target.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = target.open('w', encoding='utf-8', buffering=1)
    initialize_data_root()
    for name in ('cache', 'logs', 'models'):
        (ROOT / name).mkdir(exist_ok=True)
    if args.worker:
        try:
            return run_worker(json.loads(args.worker.read_text(encoding='utf-8')))
        except Exception as exc:
            emit('fatal', text=str(exc))
            traceback.print_exc(file=sys.stderr)
            return 1
    if args.self_check or args.download_model:
        prepare_runtime()
        import ctranslate2
        from faster_whisper import WhisperModel
        device = 'cuda' if ctranslate2.get_cuda_device_count() else 'cpu'
        print(json.dumps({'ffmpeg': ffmpeg_path(), 'frozen': FROZEN, 'portable': PORTABLE,
                          'app_dir': str(APP_DIR), 'data_dir': str(ROOT),
                          'cuda_devices': ctranslate2.get_cuda_device_count(),
                          'compute_types': sorted(ctranslate2.get_supported_compute_types(device))}, indent=2))
        if args.download_model:
            model = load_model(args.download_model)
            print('GPU model loaded successfully')
        return 0
    show_gui(args.files, args.smoke_job)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
