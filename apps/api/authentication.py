from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class SocietyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = getattr(user, 'role', 'member')
        return token


class SocietyTokenObtainPairView(TokenObtainPairView):
    serializer_class = SocietyTokenObtainPairSerializer
