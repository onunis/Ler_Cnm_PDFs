import csv
import re
import sys
from pathlib import Path

import numpy as np
import pymupdf as fitz

MAX_PAGINAS = 5  # quantas paginas tentar, em ordem, ate achar um CNM valido

CNM_RE = re.compile(r"(\d{6})\s*[.,]\s*(\d)\s*[.,]\s*(\d{7})\s*[-\u2013\u2014]\s*(\d{2})")

# (x0, y0, x1, y1, zoom): fracoes da pagina, do recorte mais justo ao mais largo
RECORTES = [(0.45, 0.0, 1.0, 0.15, 3),
            (0.30, 0.0, 1.0, 0.22, 3),
            (0.0, 0.0, 1.0, 0.30, 4)]


def dv_ok(cns, flag, mat, dv):
    n = int(cns + flag + mat + "00")
    return 98 - (n % 97) == int(dv)


def achar_cnm(texto):
    candidatos = []
    for m in CNM_RE.finditer(texto):
        cns, flag, mat, dv = m.groups()
        candidatos.append((f"{cns}.{flag}.{mat}-{dv}", dv_ok(cns, flag, mat, dv)))
    for c in candidatos:
        if c[1]:
            return c
    return candidatos[0] if candidatos else (None, False)


def matricula_do_cnm(cnm):
    """'089425.2.0478532-87' -> '478532' (7 digitos do meio, sem zeros a esquerda)."""
    if not cnm:
        return ""
    return cnm[9:16].lstrip("0")


def ocr_regiao(ocr, pagina, x0, y0, x1, y1, zoom):
    r = pagina.rect
    clip = fitz.Rect(r.x0 + r.width * x0, r.y0 + r.height * y0,
                     r.x0 + r.width * x1, r.y0 + r.height * y1)
    pix = pagina.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip,
                            colorspace=fitz.csRGB, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    resultado, _ = ocr(img)
    return " ".join(item[1] for item in (resultado or []))


def ler_pagina(pagina, ocr):
    """Devolve (cnm, validado, origem) de uma pagina."""
    cnm, ok = achar_cnm(pagina.get_text())
    if cnm and ok:
        return cnm, True, "texto"
    for x0, y0, x1, y1, zoom in RECORTES:
        texto = ocr_regiao(ocr, pagina, x0, y0, x1, y1, zoom)
        c, v = achar_cnm(texto)
        if c and v:
            return c, True, "ocr"
        if c and not cnm:
            cnm = c  # leitura nao validada, guardada so para revisao
    return cnm, False, "ocr" if cnm else "nao encontrado"


def processar(pdf, ocr):
    """Devolve (cnm, validado, origem, pagina). Tenta pagina 1, depois 2, 3..."""
    doc = fitz.open(pdf)
    if doc.page_count == 0:
        return None, False, "pdf vazio", ""
    melhor = (None, False, "nao encontrado", "")
    for i in range(min(doc.page_count, MAX_PAGINAS)):
        cnm, ok, origem = ler_pagina(doc[i], ocr)
        if cnm and ok:
            return cnm, True, origem, i + 1
        if cnm and not melhor[0]:
            melhor = (cnm, False, origem, i + 1)  # leitura duvidosa, para revisar
    return melhor


CABECALHO = ["chave", "arquivo", "cnm", "matricula", "status", "origem", "pagina"]


def salvar(linhas, saida):
    """Grava o .csv e, se o openpyxl estiver instalado, tambem um .xlsx (colunas ja separadas)."""
    with open(saida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\r\n")
        w.writerow(CABECALHO)
        w.writerows(linhas)
    try:
        from openpyxl import Workbook
    except ImportError:
        print("Aviso: para gerar tambem o .xlsx, rode: python -m pip install openpyxl")
        return None
    wb = Workbook()
    ws = wb.active
    ws.title = "cnm"
    ws.append(CABECALHO)
    for l in linhas:
        linha = list(l)
        for k in (0, 3):  # chave e matricula como numero, para o PROCV
            if str(linha[k]).isdigit():
                linha[k] = int(linha[k])
        ws.append(linha)
        for k in (1, 4):  # colunas A e D: formato numero inteiro
            ws.cell(row=ws.max_row, column=k).number_format = "0"
    for col, larg in zip("ABCDEFG", (16, 52, 24, 12, 10, 10, 8)):
        ws.column_dimensions[col].width = larg
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    destino = Path(saida).with_suffix(".xlsx")
    wb.save(destino)
    return destino


def rodando_como_exe():
    return getattr(sys, "frozen", False)


def pasta_padrao():
    """No .exe, a pasta onde ele esta; no Python normal, a pasta atual."""
    return Path(sys.executable).parent if rodando_como_exe() else Path(".")


def main():
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else pasta_padrao()
    saida = Path(sys.argv[2]) if len(sys.argv) > 2 else pasta / "cnm_extraidos.csv"
    pdfs = sorted(p for p in pasta.rglob("*") if p.suffix.lower() == ".pdf")
    if not pdfs:
        sys.exit(f"Nenhum PDF em {pasta.resolve()}")

    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()

    linhas = []
    for i, pdf in enumerate(pdfs, 1):
        try:
            cnm, ok, origem, pag = processar(pdf, ocr)
        except Exception as e:
            cnm, ok, origem, pag = None, False, f"erro: {e}", ""
        status = "OK" if ok else "REVISAR"
        print(f"[{i}/{len(pdfs)}] {pdf.name}: CNM {cnm or '-'} | matricula {matricula_do_cnm(cnm) or '-'} ({status}, {origem}, pag. {pag or '-'})")
        m = re.match(r"\d{12}", pdf.name)
        chave = m.group(0) if m else ""
        linhas.append([chave, pdf.name, cnm or "", matricula_do_cnm(cnm), status, origem, pag])

    xlsx = salvar(linhas, saida)
    revisar = sum(1 for l in linhas if l[4] != "OK")
    print(f"\nPronto: {len(linhas)} PDFs, {len(linhas) - revisar} validados, {revisar} para revisar.\nCSV: {saida.resolve()}" + (f"\nExcel: {xlsx.resolve()}" if xlsx else ""))


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        if e.code not in (None, 0):
            print(e.code)
    except Exception as e:
        print(f"Erro inesperado: {e}")
    if rodando_como_exe():
        input("\nPressione Enter para fechar...")