import markdown
from rest_framework import serializers
from .models import Category, Tag, Post
from django.contrib.auth import get_user_model

User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']


class PostSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    cover_image = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'content', 'tags', 'author_username', 
            'status', 'created_at', 'updated_at', 'cover_image'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def get_cover_image(self, obj):
        request = self.context.get('request')
        if obj.cover_image and hasattr(obj.cover_image, 'url'):
            return request.build_absolute_uri(obj.cover_image.url)
        return None