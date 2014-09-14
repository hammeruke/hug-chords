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

class IncludePdf(rst.Directive):
    """A custom directive that allows to include an entire pdf in the document
    """
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {}
    has_content = False

    def run(self):
        node = IncludedPdfElement(filename=self.arguments[0])
        return [node]

directives.register_directive("include-pdf", IncludePdf)


#
# This is the bit that merges rst2pdf with reportlab. Here we only build the
# new flowable when we find the docutils node representing it. The real action
# will be performed later, when the flowable's apply() is called.
#

from rst2pdf.basenodehandler import NodeHandler


class IncludedPdfElement(Element):
    #def gen_flowable(self, style_options):
    def gen_flowable(self):
        return IncludedPdfFlowable(self.attributes)

class HandleIncludedPdf(NodeHandler, IncludedPdfElement):
    def gather_elements(self, client, node, style):
        # style_options = {
        #     'font': client.styles['aafigure'].fontName,
        #     }
        # return [node.gen_flowable(style_options)]
        return [node.gen_flowable()]


#
# The flowable lives in reportlab. Maintain the page count after the inclusion
# of a new pdf and record the inclusion position.
# TODO: Probably must add a toc element of some sort
#

from collections import namedtuple
from reportlab.platypus.doctemplate import FrameActionFlowable
from reportlab.platypus import PageBreak
from pyPdf import PdfFileReader, PdfFileWriter

Joint = namedtuple("Joint", "start length file")
joints = []

class IncludedPdfFlowable(FrameActionFlowable):
    def __init__(self, attrs):
        self.attrs = attrs

    def frameAction(self, frame):
        # Read the number of pages of the doc to merge
        # Only once: we end up here once per document pass.
        fn = self.attrs['filename']
        if not hasattr(self, 'npages'):
            f = open(fn)
            pdf = PdfFileReader(f)
            self.npages = pdf.getNumPages()
            f.close()

        # Leave as many pages empty as the document read
        if not frame._atTop:
            frame.add_generated_content(PageBreak())
        for i in range(self.npages):
            frame.add_generated_content(PageBreak())

        # Mistery. Base zero.
        start = frame._pagenum - (frame._atTop and 1 or 0)

        # if we are on a second run clear the stored joints position
        # and start again
        if joints and joints[-1].start > start:
            del joints[:]
        joints.append(Joint(start, self.npages, fn))


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
