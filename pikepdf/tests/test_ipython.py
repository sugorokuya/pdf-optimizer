# SPDX-FileCopyrightText: 2022 James R. Barlow
# SPDX-License-Identifier: CC0-1.0

"""
Test IPython/Jupyter display hooks
"""

from __future__ import annotations

import subprocess
from io import BytesIO

import pytest
from conftest import fails_if_no_mutool

import pikepdf


@pytest.fixture
def pal(resources):
    return pikepdf.open(resources / 'pal-1bit-trivial.pdf')


def test_display_raw_page(pal):
    raw_page0 = pal.pages[0]
    mimebundle = raw_page0._repr_mimebundle_(
        include=['application/pdf'], exclude=['application/malware']
    )
    assert 'application/pdf' in mimebundle


def test_display_rich_page(pal):
    page0 = pal.pages[0]
    mimebundle = page0._repr_mimebundle_(
        include=['application/pdf'], exclude=['application/malware']
    )
    assert 'application/pdf' in mimebundle


def test_draw_page(pal, monkeypatch):
    # Test page drawing error handling independent of whether mudraw is installed

    page0 = pal.pages[0]

    def raise_filenotfound(prog_args, *args, **kwargs):
        raise FileNotFoundError(prog_args[0])

    monkeypatch.setattr(pikepdf._methods, 'run', raise_filenotfound)
    mimebundle = page0._repr_mimebundle_(
        include=['image/png'], exclude=['application/pdf']
    )
    assert (
        'image/png' not in mimebundle
    ), "Generated image/png when mudraw() was rigged to fail"

    def mudraw_return_svg(buffer, fmt):
        return b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'

    monkeypatch.setattr(pikepdf._methods, '_mudraw', mudraw_return_svg)
    mimebundle = page0._repr_mimebundle_(
        include=['image/svg+xml'], exclude=['application/pdf']
    )
    assert (
        'image/svg+xml' in mimebundle
    ), "Did not generate image/svg+xml when mudraw() was rigged to succeed"


def test_display_image(pal):
    im0 = pal.pages[0].Resources.XObject['/Im0']
    pim = pikepdf.PdfImage(im0)
    result = pim._repr_png_()
    assert result[1:4] == b'PNG'


@fails_if_no_mutool
def test_display_pdf(pal):
    mimebundle = pal._repr_mimebundle_(
        include=['application/pdf'], exclude=['text/css']
    )
    assert 'application/pdf' in mimebundle and mimebundle['application/pdf'].startswith(
        b'%PDF'
    )


def test_object_key_completion(pal):
    page0 = pal.pages[0]
    assert '/Type' in page0._ipython_key_completions_()
    assert page0.MediaBox._ipython_key_completions_() is None
