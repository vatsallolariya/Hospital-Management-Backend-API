from rest_framework.routers import DefaultRouter

from .views import HeadquartersViewSet, SubHeadquartersViewSet

router = DefaultRouter()
router.register('headquarters', HeadquartersViewSet, basename='headquarters')
router.register('sub-headquarters', SubHeadquartersViewSet, basename='sub-headquarters')

urlpatterns = router.urls
