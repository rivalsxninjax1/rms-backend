from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserCreateSerializer, UserPublicSerializer

@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    """POST /api/auth/register/ -> returns user + JWT (auto-login)"""
    serializer = UserCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    user = serializer.save()
    refresh = RefreshToken.for_user(user)
    return Response({
        "user": UserPublicSerializer(user).data,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }, status=status.HTTP_201_CREATED)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """GET /api/auth/me/ -> current profile"""
    return Response(UserPublicSerializer(request.user).data)
