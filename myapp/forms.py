from django import forms

class UpLoadPdf(forms.Form):
    name=forms.CharField(max_length=50)
    pdf_file=forms.FileField()