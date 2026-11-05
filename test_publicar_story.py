import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import publicar_story as ps


class FalsaAPI:
    """Responde como o Instagram e guarda as chamadas recebidas."""

    def __init__(self, status="FINISHED"):
        self.status = status
        self.chamadas = []

    def __call__(self, metodo, caminho, token, **params):
        self.chamadas.append((metodo, caminho, params))
        if caminho == "me":
            return {"user_id": "42", "username": "conta_teste"}
        if caminho == "42/media":
            return {"id": "c1"}
        if caminho == "c1":
            return {"status_code": self.status, "status": self.status}
        if caminho == "42/media_publish":
            return {"id": "m1"}
        raise AssertionError(f"chamada inesperada: {caminho}")

    def caminhos(self):
        return [c[1] for c in self.chamadas]

    def params_de(self, caminho):
        return next(c[2] for c in self.chamadas if c[1] == caminho)


class TesteBase(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        raiz = Path(pasta.name)
        (raiz / "fila").mkdir()
        (raiz / "publicados").mkdir()
        self.fila, self.publicados = raiz / "fila", raiz / "publicados"
        self.registro = self.publicados / "registro.csv"
        self.api = FalsaAPI()
        for alvo, valor in [
            ("FILA", self.fila),
            ("PUBLICADOS", self.publicados),
            ("REGISTRO", self.registro),
            ("chamar_api", self.api),
            ("ESPERA_STATUS_SEGUNDOS", 0),
        ]:
            patcher = mock.patch.object(ps, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        ambiente = mock.patch.dict(os.environ, {
            "INSTAGRAM_ACCESS_TOKEN": "token-teste",
            "GITHUB_REPOSITORY": "dono/repo",
            "GITHUB_SHA": "abc123",
        })
        ambiente.start()
        self.addCleanup(ambiente.stop)

    def criar(self, *nomes):
        for nome in nomes:
            (self.fila / nome).write_bytes(b"x")


class Fila(TesteBase):
    def test_publica_primeiro_em_ordem_alfabetica(self):
        self.criar("002.jpg", "001.jpg")
        self.assertEqual(ps.main(["publicar"]), 0)
        self.assertTrue((self.publicados / "001.jpg").exists())
        self.assertTrue((self.fila / "002.jpg").exists())

    def test_ignora_formato_nao_aceito_e_gitkeep(self):
        self.criar(".gitkeep", "000.png", "001.JPG")
        self.assertEqual(ps.main(["publicar"]), 0)
        self.assertTrue((self.publicados / "001.JPG").exists())
        self.assertTrue((self.fila / "000.png").exists())

    def test_fila_vazia_falha_sem_chamar_api(self):
        self.criar(".gitkeep")
        self.assertEqual(ps.main(["publicar"]), 1)
        self.assertEqual(self.api.chamadas, [])


class Publicacao(TesteBase):
    def test_imagem_percorre_todo_o_fluxo(self):
        self.criar("001 promo.jpg")
        self.assertEqual(ps.main(["publicar"]), 0)
        self.assertEqual(self.api.caminhos(), ["me", "42/media", "c1", "42/media_publish"])
        params = self.api.params_de("42/media")
        self.assertEqual(params["media_type"], "STORIES")
        self.assertEqual(
            params["image_url"],
            "https://raw.githubusercontent.com/dono/repo/abc123/fila/001%20promo.jpg",
        )
        self.assertEqual(self.api.params_de("42/media_publish")["creation_id"], "c1")
        self.assertIn(",001 promo.jpg,m1", self.registro.read_text(encoding="utf-8"))

    def test_video_usa_video_url(self):
        self.criar("001.mp4")
        self.assertEqual(ps.main(["publicar"]), 0)
        self.assertIn("video_url", self.api.params_de("42/media"))

    def test_midia_rejeitada_nao_publica_e_mantem_na_fila(self):
        self.api.status = "ERROR"
        self.criar("001.jpg")
        self.assertEqual(ps.main(["publicar"]), 1)
        self.assertNotIn("42/media_publish", self.api.caminhos())
        self.assertTrue((self.fila / "001.jpg").exists())
        self.assertFalse(self.registro.exists())

    def test_processamento_sem_fim_desiste_e_mantem_na_fila(self):
        self.api.status = "IN_PROGRESS"
        self.criar("001.jpg")
        self.assertEqual(ps.main(["publicar"]), 1)
        self.assertEqual(self.api.caminhos().count("c1"), ps.TENTATIVAS_STATUS)
        self.assertTrue((self.fila / "001.jpg").exists())

    def test_sem_token_falha_sem_mover_arquivo(self):
        del os.environ["INSTAGRAM_ACCESS_TOKEN"]
        self.criar("001.jpg")
        self.assertEqual(ps.main(["publicar"]), 1)
        self.assertTrue((self.fila / "001.jpg").exists())


class UmPorDia(TesteBase):
    def test_segunda_execucao_no_dia_nao_publica(self):
        self.criar("001.jpg", "002.jpg")
        ps.main(["publicar"])
        self.api.chamadas.clear()
        self.assertEqual(ps.main(["publicar"]), 0)
        self.assertEqual(self.api.chamadas, [])
        self.assertTrue((self.fila / "002.jpg").exists())

    def test_forcar_publica_de_novo_no_mesmo_dia(self):
        self.criar("001.jpg", "002.jpg")
        ps.main(["publicar"])
        self.assertEqual(ps.main(["publicar", "--forcar"]), 0)
        self.assertTrue((self.publicados / "002.jpg").exists())

    def test_registro_de_outro_dia_nao_bloqueia(self):
        self.registro.write_text("2000-01-01,antigo.jpg,m0\n", encoding="utf-8")
        self.criar("001.jpg")
        self.assertEqual(ps.main(["publicar"]), 0)
        self.assertTrue((self.publicados / "001.jpg").exists())


class Simulacao(TesteBase):
    def test_nao_chama_api_nem_move_arquivo(self):
        self.criar("001.jpg")
        self.assertEqual(ps.main(["simulacao"]), 0)
        self.assertEqual(self.api.chamadas, [])
        self.assertTrue((self.fila / "001.jpg").exists())


if __name__ == "__main__":
    unittest.main()
