"""
rst2pdf extension to build a songbook.

The songbook is a mix of a normal reST document (to render as PDF) and a set of
songbooks rendered by other means and available as pdf.

Currently there is a base ``include-pdf`` directive implemented. What is
planned is a tighter interaction with chordlab, e.g. to fix the page numbers in
the songsheets and read the songs titles, this kind of stuff. That's TODO.

The usage is something like::

    rst2pdf -e songbook -o sample.pdf sample.rst

See `sample.rst` for an input file example.

"""

#
# Additional reST directives that we can add to the document
#

from docutils.parsers import rst
from docutils.nodes import Element
from docutils.parsers.rst import directives

class IncludedPdfElement(Element):
    pass

class IncludePdf(rst.Directive):
    """A custom directive that allows to include an entire pdf in the document
    """
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = dict(
        title=directives.unchanged,
    )
    has_content = False

    def run(self):
        node = IncludedPdfElement(filename=self.arguments[0], **self.options)
        return [node]

directives.register_directive("include-pdf", IncludePdf)


class SongsheetElement(Element):
    pass

class Songsheet(rst.Directive):
    """Directive to include a songsheet in a document
    """
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {
        'title': directives.unchanged,
        'render-args': directives.unchanged }
    has_content = False

    def run(self):
        node = SongsheetElement(filename=self.arguments[0], **self.options)
        return [node]

directives.register_directive("song", Songsheet)


#
# This is the bit that merges rst2pdf with reportlab. Here we only build the
# new flowable when we find the docutils node representing it. The real action
# will be performed later, when the flowable's apply() is called.
#

from rst2pdf.basenodehandler import NodeHandler

class HandleIncludedPdf(NodeHandler, IncludedPdfElement):
    def gather_elements(self, client, node, style):
        level = client.depth
        return [ IncludedPdfFlowable(node, level, style) ]

class HandleSongsheet(NodeHandler, SongsheetElement):
    def gather_elements(self, client, node, style):
        level = client.depth
        return [ SongsheetFlowable(node, level, style) ]

#
# The flowable lives in reportlab. Maintain the page count after the inclusion
# of a new pdf and record the inclusion position.
# TODO: Probably must add a toc element of some sort
#

from collections import namedtuple
from reportlab.platypus.doctemplate import FrameActionFlowable
from reportlab.platypus import PageBreak
from rst2pdf.flowables import Heading, Paragraph
from pyPdf import PdfFileReader, PdfFileWriter

Joint = namedtuple("Joint", "start length file")
joints = []

class IncludedPdfFlowable(FrameActionFlowable):
    def __init__(self, node, level, style):
        self.node = node
        self.level = level
        self.style = style

    def frameAction(self, frame):
        self.include_pdf(frame, self.node.attributes['filename'])

    def include_pdf(self, frame, filename):
        # Read the number of pages of the doc to merge
        # Only once: we end up here once per document pass.
        if not hasattr(self, 'npages'):
            f = open(filename)
            pdf = PdfFileReader(f)
            self.npages = pdf.getNumPages()
            f.close()

        # Finish the current page if already started.
        if not frame._atTop:
            frame.add_generated_content(PageBreak())

        # Add a toc entry for the part inserted.
        if 'title' in self.node.attributes:
            parent_id = (self.node.parent.get('ids', [None]) or [None])[0] \
                    + u'-' + unicode(id(self.node))
            frame.add_generated_content(PdfTocEntry(
                text=self.node.attributes['title'],
                style=self.style,
                level=self.level,
                parent_id=parent_id,
                node=self.node))

        # Leave as many pages empty as the document read.
        for i in range(self.npages):
            frame.add_generated_content(PageBreak())

        # Mistery. Base zero.
        start = frame._pagenum - (frame._atTop and 1 or 0)

        # if we are on a second run clear the stored joints position
        # and start again
        if joints and joints[-1].start > start:
            del joints[:]
        joints.append(Joint(start, self.npages, filename))


import re
import shlex
import atexit
from tempfile import NamedTemporaryFile
from subprocess import check_call

class SongsheetFlowable(IncludedPdfFlowable):
    _tempfile = None
    _page = None

    def frameAction(self, frame):
        fn = self.node.attributes['filename']
        # the mystery formula...
        page = frame._pagenum - (frame._atTop and 1 or 0) + 1

        # don't re-render the songsheet pdf if the page number hasn't changed
        if page != self._page:
            self._page = page
            self.render_cho(frame, fn)

        if 'title' not in self.node.attributes:
            self.node.attributes['title'] = self.get_title(fn)

        self.include_pdf(frame, self.get_temp_filename())

    def render_cho(self, page, filename):
        cmdline = [ '../../env/bin/chordlab']   # TODO: stub
        # TODO: also fix chordlab search for fonts in the stylesheet
        # paths should be relative from the stylesheet, not from cwd.
        if 'render-args' in self.node.attributes:
            cmdline.extend(shlex.split(self.node.attributes['render-args']))

        # TODO: pass a start page number to chordlab
        # cmdline.extend(['--start-page', str(page)])

        outfn = self.get_temp_filename()
        cmdline.extend(['-o', outfn])
        cmdline.append(filename)

        check_call(cmdline)

    def get_temp_filename(self):
        if self._tempfile is not None:
            return self._tempfile.name

        t = self._tempfile = NamedTemporaryFile(suffix='.pdf', delete=False)
        t.close()
        atexit.register(os.unlink, t.name)
        return t.name

    def get_title(self, fn):
        # Parse the .cho to get title and subtitle
        title = author = None
        rex = re.compile(r'^\s*{(t|st):([^}]+)}\s*$')
        for line in open(fn):
            m = rex.match(line)
            if m is None: continue
            if m.group(1) == 't':
                title = m.group(2)
            elif m.group(1) == 'st':
                author = m.group(2)
            if title is not None and author is not None:
                break

        if not title:
            title = os.path.splitext(os.path.split(fn)[-1])[0].title() \
                    .replace('-', ' ')

        if author:
            title += ' - ' + author

        return title


class PdfTocEntry(Heading):
    """An outline entry in the PDF TOC pointing to an inserted PDF"""
    def draw(self):
        self.canv.bookmarkHorizontal(self.parent_id,0,0 + self.height)
        self.canv.addOutlineEntry(
            self.stext.encode('utf-8','replace'),
            self.parent_id.encode('utf-8','replace'),
            int(self.level), False)
        Paragraph.draw(self)


#
# Monkeypatching of rst2pdf
# After the creation of the original document merge it with the other pieces.
#

import os
from rst2pdf import createpdf

class JoiningRstToPdf(createpdf.RstToPdf):
    def createPdf(self, output, **kwargs):
        tmpfile = output + '.tmp'
        super(JoiningRstToPdf, self).createPdf(output=tmpfile, **kwargs)

        openfiles = []  # the pdf libraries wants the files open when writing

        # Open the file just generated
        f = open(tmpfile)
        openfiles.append(f)
        doc = PdfFileReader(f)

        pdf = PdfFileWriter()
        docpage = 0
        for joint in joints:
            # Add the document pages before this joint
            for i in range(docpage, joint.start):
                pdf.addPage(doc.getPage(i))

            # add the merged document
            f1 = open(joint.file)
            openfiles.append(f1)
            doc1 = PdfFileReader(f1)
            assert doc1.getNumPages() == joint.length
            for i in xrange(doc1.getNumPages()):
                pdf.addPage(doc1.getPage(i))

            docpage = joint.start + joint.length

        # Add the last pages of the doc
        for i in range(docpage, doc.getNumPages()):
            pdf.addPage(doc.getPage(i))

        # Write the joined file
        f = open(output, 'wb')
        pdf.write(f)
        f.close()

        # Now close everything you got open
        for f in openfiles:
            f.close()

        os.unlink(tmpfile)


def install(createpdf, options):
    createpdf.RstToPdf = JoiningRstToPdf
