from django.contrib.auth import get_user_model, authenticate
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

def _jwt_pair_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    data = request.data or {}
    username = data.get("username") or (data.get("email") or "").split("@")[0]
    email = data.get("email")
    password = data.get("password") or User.objects.make_random_password()
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")

    if not email:
        return Response({"email": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=username).exists():
        return Response({"username": ["Username already taken."]}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(email=email).exists():
        return Response({"email": ["Email already used."]}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, email=email, password=password,
                                    first_name=first_name, last_name=last_name)
    tokens = _jwt_pair_for_user(user)
    return Response(tokens, status=status.HTTP_201_CREATED)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    u = request.user
    return Response({
        "id": u.id, "username": u.username, "email": u.email,
        "first_name": u.first_name, "last_name": u.last_name
    })
