#!/usr/bin/env python
"""Os "ouvidos" do lado Crash: passa os sons extraídos pelo Whisper para descobrir qual é qual (o "Woah!").

Precisa do faster-whisper (não está no requirements.txt: é só para esta conferência). Nós rodamos com o Python
do estúdio de vídeo do ByteMirage, que já tem o faster-whisper e o modelo "medium" em cache:

    set ESTUDIO_DE_VIDEO=<pasta do estúdio, com cache/hf dentro>
    "<esse Python>" -I ouvir_sons.py [nomes...]

Sem a variável, usa o cache padrão do Hugging Face (e baixa o modelo na primeira vez).

Cada som é ouvido em mais de uma taxa, porque no Crash 1 quem escolhe o tom é o script na hora de tocar
(`soundpitch`). O Whisper inventa palavra em barulho curto: o resultado é pista, não prova.
"""
import json
import os
import struct
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
ESTUDIO = os.environ.get('ESTUDIO_DE_VIDEO', '')
if ESTUDIO:                                                    # modelo já baixado: não vai à rede
    os.environ.setdefault('HF_HOME', os.path.join(ESTUDIO, 'cache', 'hf'))
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')

from faster_whisper import WhisperModel                        # noqa: E402

TAXAS = (11025, 8500, 22050)


def pcm_do_wav(caminho):
    with open(caminho, 'rb') as f:
        d = f.read()
    pos = d.index(b'data') + 8
    return np.frombuffer(d[pos:], '<i2').astype(np.float32) / 32768.0


def para_16k(amostras, taxa):
    n = int(len(amostras) * 16000 / taxa)
    if n < 2:
        return np.zeros(16000, np.float32)
    x = np.interp(np.linspace(0, len(amostras) - 1, n), np.arange(len(amostras)), amostras).astype(np.float32)
    return np.concatenate([np.zeros(4000, np.float32), x, np.zeros(4000, np.float32)])


def principal():
    sys.stdout.reconfigure(encoding='utf-8')
    pasta = os.path.join(AQUI, 'out', 'snd')
    nomes = sys.argv[1:] or sorted(a[:-4] for a in os.listdir(pasta) if a.endswith('.wav'))
    raiz = os.path.join(os.environ['HF_HOME'], 'whisper') if 'HF_HOME' in os.environ else None
    modelo = WhisperModel('medium', device='cpu', compute_type='int8', download_root=raiz)
    resultado = {}
    for nome in nomes:
        pcm = pcm_do_wav(os.path.join(pasta, nome + '.wav'))
        pico = float(np.abs(pcm).max()) if len(pcm) else 0.0
        linha = {}
        for taxa in TAXAS:
            segs, _ = modelo.transcribe(para_16k(pcm, taxa), language='en', beam_size=5,
                                        condition_on_previous_text=False, no_speech_threshold=0.9)
            linha[taxa] = ' '.join(s.text.strip() for s in segs)
        resultado[nome] = linha
        print(f'{nome:6} {len(pcm):6} amostras, pico {pico:.2f} | ' +
              ' | '.join(f'{t} Hz: "{linha[t]}"' for t in TAXAS), flush=True)
    with open(os.path.join(AQUI, 'out', 'snd', 'whisper.json'), 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    principal()
