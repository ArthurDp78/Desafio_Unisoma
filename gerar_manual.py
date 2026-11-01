"""Converte o HTML do manual em PDF apenas na preparação/build da aplicação."""
from argparse import ArgumentParser
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

from ui.recursos import NOME_MANUAL

RAIZ = Path(__file__).resolve().parent


def gerar_manual(html: Path, destino: Path) -> Path:
    """Renderiza o CSS de impressão com Chromium, sem dependências na aplicação."""
    from playwright.sync_api import sync_playwright

    html = html.resolve(strict=True)
    destino = destino.resolve()
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Só substitui o PDF anterior depois que a conversão termina com sucesso.
    with TemporaryDirectory(prefix=".manual-", dir=destino.parent) as temporario:
        pdf = Path(temporario) / NOME_MANUAL
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.emulate_media(media="print")
                page.goto(html.as_uri(), wait_until="load")
                page.evaluate("""async () => {
                    await document.fonts.ready;
                    await Promise.all(Array.from(document.images, image => image.decode()));
                }""")
                page.pdf(
                    path=str(pdf),
                    format="A4",
                    prefer_css_page_size=True,
                    print_background=True,
                    display_header_footer=False,
                )
            finally:
                browser.close()
        if not pdf.read_bytes().startswith(b"%PDF-"):
            raise RuntimeError("A conversão não produziu um PDF válido.")
        pdf.replace(destino)
    return destino


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, default=RAIZ / "manual_usuario.html")
    parser.add_argument("--destino", type=Path, default=RAIZ / NOME_MANUAL)
    args = parser.parse_args()
    try:
        destino = gerar_manual(args.html, args.destino)
    except Exception as erro:
        print(f"Falha ao gerar o manual: {erro}", file=sys.stderr)
        print(
            "Prepare o ambiente com: python -m pip install -r requirements-dev.txt\n"
            "python -m playwright install chromium --only-shell",
            file=sys.stderr,
        )
        return 1
    print(f"Manual gerado em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
