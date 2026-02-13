from celery import shared_task
from .models import Loan, Member
from django.db.models import Prefetch, Count

from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass

@shared_task
def check_overdue_loans():
    try:

        loans = Prefetch(
            "loans",
            queryset=Loan.objects.filter(is_returned=False,due_date__lt=timezone.now().date())
        )

        members = Member.objects.prefetch_related(loans) \
                .annotate(num_loans = Count("loans", distinct=True)) \
                .filter(num_loans__gt=0)
        
        for member in members:
            send_mail(
                subject='Overdue Books',
                message=f'Hello {member.user.username},\n\nYou have {member.num_loans} overdue books',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member.user.email],
                fail_silently=False,
            )

    except Exception as e:
        pass
