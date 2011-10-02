from unittest import TestCase
from sys import version_info
try:
    from functools import wraps
except ImportError:
    from django.utils.functional import wraps  # Python 2.3, 2.4 fallback.

from django.http import HttpResponse, HttpRequest
from django.utils.functional import allow_lazy, lazy, memoize
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.vary import vary_on_headers, vary_on_cookie
from django.views.decorators.cache import cache_page, never_cache, cache_control
from django.utils.decorators import auto_adapt_to_methods
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required

def fully_decorated(request):
    """Expected __doc__"""
    return HttpResponse('<html><body>dummy</body></html>')
fully_decorated.anything = "Expected __dict__"

# django.views.decorators.http
fully_decorated = require_http_methods(["GET"])(fully_decorated)
fully_decorated = require_GET(fully_decorated)
fully_decorated = require_POST(fully_decorated)

# django.views.decorators.vary
fully_decorated = vary_on_headers('Accept-language')(fully_decorated)
fully_decorated = vary_on_cookie(fully_decorated)

# django.views.decorators.cache
fully_decorated = cache_page(60*15)(fully_decorated)
fully_decorated = cache_control(private=True)(fully_decorated)
fully_decorated = never_cache(fully_decorated)

# django.contrib.auth.decorators
# Apply user_passes_test twice to check #9474
fully_decorated = user_passes_test(lambda u:True)(fully_decorated)
fully_decorated = login_required(fully_decorated)
fully_decorated = permission_required('change_world')(fully_decorated)

# django.contrib.admin.views.decorators
fully_decorated = staff_member_required(fully_decorated)

# django.utils.functional
fully_decorated = memoize(fully_decorated, {}, 1)
fully_decorated = allow_lazy(fully_decorated)
fully_decorated = lazy(fully_decorated)

class DecoratorsTest(TestCase):

    def test_attributes(self):
        """
        Tests that django decorators set certain attributes of the wrapped
        function.
        """
        # Only check __name__ on Python 2.4 or later since __name__ can't be
        # assigned to in earlier Python versions.
        if version_info[0] >= 2 and version_info[1] >= 4:
            self.assertEquals(fully_decorated.__name__, 'fully_decorated')
        self.assertEquals(fully_decorated.__doc__, 'Expected __doc__')
        self.assertEquals(fully_decorated.__dict__['anything'], 'Expected __dict__')

    def test_user_passes_test_composition(self):
        """
        Test that the user_passes_test decorator can be applied multiple times
        (#9474).
        """
        def test1(user):
            user.decorators_applied.append('test1')
            return True
            
        def test2(user):
            user.decorators_applied.append('test2')
            return True
            
        def callback(request):
            return request.user.decorators_applied

        callback = user_passes_test(test1)(callback)
        callback = user_passes_test(test2)(callback)
        
        class DummyUser(object): pass
        class DummyRequest(object): pass
        
        request = DummyRequest()
        request.user = DummyUser()
        request.user.decorators_applied = []
        response = callback(request)
        
        self.assertEqual(response, ['test2', 'test1'])

    def test_cache_page_new_style(self):
        """
        Test that we can call cache_page the new way
        """
        def my_view(request):
            return "response"
        my_view_cached = cache_page(123)(my_view)
        self.assertEqual(my_view_cached(HttpRequest()), "response")
        my_view_cached2 = cache_page(123, key_prefix="test")(my_view)
        self.assertEqual(my_view_cached2(HttpRequest()), "response")

    def test_cache_page_old_style(self):
        """
        Test that we can call cache_page the old way
        """
        def my_view(request):
            return "response"
        my_view_cached = cache_page(my_view, 123)
        self.assertEqual(my_view_cached(HttpRequest()), "response")
        my_view_cached2 = cache_page(my_view, 123, key_prefix="test")
        self.assertEqual(my_view_cached2(HttpRequest()), "response")

class MethodDecoratorAdapterTests(TestCase):
    def test_auto_adapt_to_methods(self):
        """
        Test that auto_adapt_to_methods actually works.
        """
        # Need 2 decorators with auto_adapt_to_methods,
        # to check it plays nicely with composing itself.

        def my_decorator(func):
            def wrapped(*args, **kwargs):
                # need to ensure that the first arg isn't 'self'
                self.assertEqual(args[0], "test")
                return "my_decorator:" + func(*args, **kwargs)
            wrapped.my_decorator_custom_attribute = True
            return wraps(func)(wrapped)
        my_decorator = auto_adapt_to_methods(my_decorator)

        def my_decorator2(func):
            def wrapped(*args, **kwargs):
                # need to ensure that the first arg isn't 'self'
                self.assertEqual(args[0], "test")
                return "my_decorator2:" + func(*args, **kwargs)
            wrapped.my_decorator2_custom_attribute = True
            return wraps(func)(wrapped)
        my_decorator2 = auto_adapt_to_methods(my_decorator2)

        class MyClass(object):
            def my_method(self, *args, **kwargs):
                return "my_method:%r %r" % (args, kwargs)
            my_method = my_decorator2(my_decorator(my_method))

        obj = MyClass()
        self.assertEqual(obj.my_method("test", 123, name='foo'),
                         "my_decorator2:my_decorator:my_method:('test', 123) {'name': 'foo'}")
        self.assertEqual(obj.my_method.__name__, 'my_method')
        self.assertEqual(getattr(obj.my_method, 'my_decorator_custom_attribute', False),
                         True)
        self.assertEqual(getattr(obj.my_method, 'my_decorator2_custom_attribute', False),
                         True)