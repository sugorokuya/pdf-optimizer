# SPDX-FileCopyrightText: 2022 James R. Barlow
# SPDX-License-Identifier: CC0-1.0

from __future__ import annotations

import sys

import pytest

from pikepdf import Dictionary, ForeignObjectError, Name, Pdf

# pylint: disable=redefined-outer-name


@pytest.fixture
def vera(resources):
    # Has XMP but no docinfo
    with Pdf.open(resources / 'veraPDF test suite 6-2-10-t02-pass-a.pdf') as pdf:
        yield pdf


@pytest.fixture
def outlines(resources):
    with Pdf.open(resources / 'outlines.pdf') as pdf:
        yield pdf


def test_no_foreign_on_direct(vera):
    direct_object = Dictionary()
    with pytest.raises(ForeignObjectError, match="called with direct object"):
        vera.copy_foreign(direct_object)


def test_must_use_copy_foreign(vera, outlines, outpdf):
    vera.Root.Names = Dictionary()
    vera.Root.Names.Dests = outlines.Root.Names.Dests
    with pytest.raises(ForeignObjectError, match="add objects from another file"):
        vera.save(outpdf)


def test_self_copy_foreign(vera):
    direct_object = Dictionary()
    indirect_object = vera.make_indirect(direct_object)
    assert indirect_object.is_indirect
    with pytest.raises(ForeignObjectError, match="called with object from"):
        vera.Root.IndirectObj = vera.copy_foreign(indirect_object)


def test_copy_foreign_copies(vera, outlines, outpdf):
    assert outlines.Root.Names.is_indirect
    assert outlines.Root.Names.is_owned_by(outlines)

    vera.Root.Names = vera.copy_foreign(outlines.Root.Names)
    assert vera.Root.Names.is_owned_by(vera)
    assert not outlines.Root.Names.is_owned_by(vera)
    vera.save(outpdf)


def test_with_same_owner_as(vera, outlines, outpdf):
    assert vera.Root.is_owned_by(vera)

    # return reference to self
    indirect_dict = vera.make_indirect(Dictionary(Foo=42))
    vera.Root.IndirectDict = indirect_dict
    vera.save(outpdf)

    # copy direct object case
    vera.Root.CopiedDirectNames = Dictionary(Foo=42).with_same_owner_as(vera.Root)
    vera.save(outpdf)

    # copy foreign case
    vera.Root.ForeignNames = outlines.Root.Names.with_same_owner_as(vera.Root)
    vera.save(outpdf)

    # invalid other owner case
    with pytest.raises(ValueError):
        outlines.Root.Names.with_same_owner_as(Dictionary(Foo=42))


def test_issue_271():
    f1 = Pdf.new()
    f2 = Pdf.new()
    p11 = f1.add_blank_page()
    # copy p1 to f2 and change its mediabox

    f2.pages.append(p11)
    p21 = f2.pages[0]
    p21.MediaBox[0] = 1
    p21.Rotate = 1

    f2.pages.append(p11)
    p22 = f2.pages[1]

    assert p21.MediaBox[0] != p11.MediaBox[0]
    assert Name.Rotate in p21
    assert Name.Rotate not in p11

    # This behavior is counterintuitive, but it is what we do, because it is what
    # qpdf does. When a page is copied from one pdf to another, qpdf caches the
    # copy and returns it.
    assert p22.MediaBox[0] != p11.MediaBox[0]
    assert p22.MediaBox[0] == p21.MediaBox[0]


def test_copy_foreign_refcount(refcount, vera, outlines):
    c = refcount(outlines.Root.Names)
    expected = c if sys.version_info >= (3, 14) else c + 1
    assert refcount(outlines.Root.Names) == expected
    vera.Root.Names = vera.copy_foreign(outlines.Root.Names)
    assert refcount(outlines.Root.Names) == expected


def test_copy_foreign_page_object(vera, outlines):
    with pytest.raises(NotImplementedError, match="Pdf.pages"):
        outlines.copy_foreign(vera.pages[0])
