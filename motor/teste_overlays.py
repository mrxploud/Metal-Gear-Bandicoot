"""Regressões do reempacotamento: recursos intactos e posições após crescer/encolher."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from overlays import SETOR, alinhar, substituir_modulos


def fase(modulo, recurso):
    cabecalho = bytearray(SETOR)
    binario = modulo + bytes(alinhar(len(modulo)) - len(modulo))
    struct.pack_into('<BBH', cabecalho, 0, 1, 0, 2 + len(binario) // SETOR)
    struct.pack_into('<HBBI', cabecalho, 4, 123, ord('s'), ord('b'), len(modulo))
    struct.pack_into('<HBBI', cabecalho, 12, 456, ord('n'), ord('d'), SETOR)
    return bytes(cabecalho) + binario + recurso * SETOR


class TesteOverlays(unittest.TestCase):
    def setUp(self):
        self.blocos = [fase(b'a' * 17, b'A'), fase(b'b' * 5000, b'B'), fase(b'c', b'C')]
        cabecalho = bytearray(SETOR)
        struct.pack_into('<I', cabecalho, 0, 36)
        setor = 1
        for i, bloco in enumerate(self.blocos):
            struct.pack_into('<8sI', cabecalho, 4 + i * 12, f's0{i}a'.encode(), setor)
            setor += len(bloco) // SETOR
        self.original = bytes(cabecalho) + b''.join(self.blocos)

    def test_crescer_encolher_preserva_recursos_e_fase_intocada(self):
        novos = {'s00a': b'x' * 7000, 's01a': b'y' * 19}
        resultado = substituir_modulos(self.original, novos)
        setor = 1
        for i, nome in enumerate(('s00a', 's01a', 's02a')):
            _, inicio = struct.unpack_from('<8sI', resultado, 4 + i * 12)
            self.assertEqual(inicio, setor)
            pos = inicio * SETOR
            nsetores = struct.unpack_from('<H', resultado, pos + 2)[0]
            bloco = resultado[pos:pos + nsetores * SETOR]
            if nome in novos:
                self.assertEqual(struct.unpack_from('<I', bloco, 8)[0], len(novos[nome]))
                self.assertEqual(bloco[SETOR:SETOR + len(novos[nome])], novos[nome])
                self.assertEqual(bloco[-SETOR:], self.blocos[i][-SETOR:])
                self.assertEqual(bloco[12:SETOR], self.blocos[i][12:SETOR])
            else:
                self.assertEqual(bloco, self.blocos[i])
            setor += nsetores
        self.assertEqual(len(resultado), setor * SETOR)

    def test_sem_modificacoes_identico(self):
        self.assertEqual(substituir_modulos(self.original, {}), self.original)

    def test_rejeita_nome_inexistente_e_bloco_invalido(self):
        with self.assertRaisesRegex(ValueError, 'ausentes'):
            substituir_modulos(self.original, {'inexist': b'x'})
        corrompido = bytearray(self.original)
        corrompido[SETOR + 6] = ord('c')
        with self.assertRaisesRegex(ValueError, 'primeiro bloco'):
            substituir_modulos(corrompido, {'s00a': b'x'})


if __name__ == '__main__':
    unittest.main()
