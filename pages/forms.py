"""Validation for the two public contact forms and their optional screenshots."""

from django import forms


def _screenshot_content_type(header):
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None


class MultipleScreenshotInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class ScreenshotsField(forms.FileField):
    """Accept a few small screenshots without requiring a media storage backend."""

    widget = MultipleScreenshotInput(attrs={"accept": "image/png,image/jpeg,image/webp"})

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data] if data else []
        if len(files) > 3:
            raise forms.ValidationError("Attach no more than three screenshots.")

        checked = []
        total_size = 0
        for upload in files:
            file = super().clean(upload, initial)
            total_size += file.size
            if file.size > 5 * 1024 * 1024 or total_size > 12 * 1024 * 1024:
                raise forms.ValidationError(
                    "Screenshots must be under 5 MB each and 12 MB together."
                )
            header = file.read(12)
            file.seek(0)
            content_type = _screenshot_content_type(header)
            if content_type is None:
                raise forms.ValidationError("Attach PNG, JPG or WebP screenshots only.")
            file.content_type = content_type
            checked.append(file)
        return checked


class PublicContactForm(forms.Form):
    email = forms.EmailField(required=False, max_length=254)
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_website(self):
        if self.cleaned_data["website"]:
            raise forms.ValidationError("Your message could not be sent.")
        return ""


class ProblemReportForm(PublicContactForm):
    description = forms.CharField(max_length=5000, widget=forms.Textarea(attrs={"rows": 4}))
    steps = forms.CharField(
        required=False, max_length=3000, widget=forms.Textarea(attrs={"rows": 4})
    )
    area = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Choose an area"),
            ("Dashboard", "Dashboard"),
            ("My work", "My work"),
            ("Contacts", "Contacts"),
            ("Properties", "Properties"),
            ("Profile", "Profile"),
            ("Somewhere else", "Somewhere else"),
        ],
    )
    screenshots = ScreenshotsField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].widget.attrs["class"] = "form-select"
        self.fields["email"].widget.attrs["autocomplete"] = "off"


class MessageForm(PublicContactForm):
    topic = forms.ChoiceField(
        choices=[
            ("Question", "Question"),
            ("Help", "Help"),
            ("Suggestion", "Suggestion"),
            ("Something else", "Something else"),
        ]
    )
    body = forms.CharField(max_length=5000, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topic"].widget.attrs["class"] = "form-select"
        self.fields["email"].widget.attrs["autocomplete"] = "off"
