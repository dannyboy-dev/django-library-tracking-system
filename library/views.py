from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer, ExtendLoanSerializer, TopActiveMemmbersSerializer
from rest_framework.decorators import action
from django.utils import timezone
from .tasks import send_loan_notification
from rest_framework.views import APIView
from django.db.models import Prefetch, Count, Q, F

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.prefetch_related(
        Prefetch("loans", Loan.objects.select_related("book","member"))
    )
    serializer_class = BookSerializer

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(detail=False, methods=['get'], url_path="top-active", serializer_class = TopActiveMemmbersSerializer)
    def top_active_members(self, request, pk=None): 
        members = Member.objects \
        .select_related("user") \
        .prefetch_related("loans") \
        .annotate(activer_loans = Count("loans",distinct=True, filter=Q(loans__is_returned=True))) \
        .annotate(member_id=F('id'),username=F('user__username'),email=F('user__email'),number_of_active_loans=F('activer_loans'),) \
        .values('member_id','username','email','number_of_active_loans')

        print(members)

        serilizer = TopActiveMemmbersSerializer(members, many=True)

        return Response(serilizer.data, status=status.HTTP_200_OK)

class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(detail=True, methods=['post'], serializer_class = ExtendLoanSerializer)
    def extend_due_date (self, request, pk=None): 
        serializer = ExtendLoanSerializer(request.data)
        serializer.is_valid(raise_exception=True)

        loan = self.get_object()
        loan.due_date += serializer.validated_data.get("additional_days")
        loan.save()
        return Response({'status': 'Loan extended successfully.'}, status=status.HTTP_200_OK)
    


