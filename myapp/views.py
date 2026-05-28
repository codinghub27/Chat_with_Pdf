from django.http import JsonResponse
from django.shortcuts import render, redirect
from .models import Profile, ChatMessage
from .forms import UpLoadPdf
from .langchain_utils import process_pdf, get_answer, retrievers
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden

@login_required
def index(request):
    pdfs = Profile.objects.filter(user=request.user)

    context = {'pdfs': pdfs}
    return render(request, 'myapp/index.html', context)


@login_required
def upload_pdf(request):
    form = UpLoadPdf()
    if request.method == "POST":
        form = UpLoadPdf(request.POST, request.FILES)
        if form.is_valid():
            pdf = Profile.objects.create(
                user=request.user,
                name=form.cleaned_data['name'],
                pdf=form.cleaned_data['pdf_file']
            )
            retrievers[pdf.id] = process_pdf(
                pdf.pdf.path,pdf.id
            )
            return redirect('index')
    context = {'form': form}
    return render(request, 'myapp/upload.html', context)


@login_required
def chat_view(request, pdf_id):
    pdf = get_object_or_404(Profile, id=pdf_id)
    if pdf.user != request.user:
        return HttpResponseForbidden("You are not allowed to access this PDF.")

    if request.method == "POST":
        question = request.POST.get('question')

        # rebuild retriever if not in memory (e.g. after server restart)
        if pdf_id not in retrievers:
            retrievers[pdf_id] = process_pdf(pdf.pdf.path,pdf_id)

        retriever = retrievers[pdf_id]
        answer = get_answer(retriever, question, request.user.id, pdf_id)
        ChatMessage.objects.create(
            pdf=pdf,
            user=request.user,
            question=question,
            answer=answer
        )
        return JsonResponse({'answer': answer})
    messages = ChatMessage.objects.filter(pdf=pdf, user=request.user).order_by('created_at')
    return render(request, 'myapp/chat.html', {'pdf_id': pdf_id,'messages':messages})


@login_required
def delete_view(request, pdf_id):
    pdf = get_object_or_404(Profile, id=pdf_id)
    if pdf.user != request.user:
        return HttpResponseForbidden("You are not allowed to delete this PDF.")
    pdf.delete()
    return redirect('index')