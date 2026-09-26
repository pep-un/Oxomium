from django.template import Context, Template
from django.test import SimpleTestCase

from conformity.templatetags.attachment_tags import attachment_icon


class AttachmentIconTests(SimpleTestCase):
    def test_known_mime_families(self):
        cases = {
            "application/pdf": "bi-file-earmark-pdf",
            "image/png": "bi-file-earmark-image",
            "text/plain": "bi-file-earmark-text",
            "application/msword": "bi-file-earmark-text",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "bi-file-earmark-text",
            "application/vnd.ms-excel": "bi-file-earmark-spreadsheet",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "bi-file-earmark-spreadsheet",
            "application/zip": "bi-file-earmark-zip",
        }
        for mime_type, expected in cases.items():
            with self.subTest(mime_type=mime_type):
                self.assertEqual(attachment_icon(mime_type), expected)

    def test_unknown_or_empty_mime_uses_generic_file_icon(self):
        self.assertEqual(attachment_icon("application/x-unknown"), "bi-file-earmark")
        self.assertEqual(attachment_icon(""), "bi-file-earmark")
        self.assertEqual(attachment_icon(None), "bi-file-earmark")

    def test_mime_parameters_and_case_are_normalized(self):
        self.assertEqual(attachment_icon("IMAGE/PNG; charset=binary"), "bi-file-earmark-image")

    def test_shared_component_keeps_filename_link_and_secondary_mime(self):
        class AttachmentStub:
            id = 42
            mime_type = "application/pdf"

            def __str__(self):
                return "report.pdf"

        attachment = AttachmentStub()
        template = Template('{% include "includes/attachment_link.html" with attachment=attachment %}')
        html = template.render(Context({"attachment": attachment}))
        self.assertIn("bi-file-earmark-pdf", html)
        self.assertIn("report.pdf", html)
        self.assertIn('title="application/pdf"', html)
        self.assertIn("/attachment/42/", html)
        self.assertIn('aria-hidden="true"', html)
        self.assertNotIn(">application/pdf<", html)
