##############################################################################
#
# Copyright (c) 2002 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Adapters for the traversing mechanism
"""
from types import StringTypes

import zope.interface
import zope.component

from zope.location.interfaces import ILocationInfo, LocationError
from zope.traversing.interfaces import ITraversable, ITraverser

from zope.traversing.namespace import namespaceLookup
from zope.traversing.namespace import UnexpectedParameters
from zope.traversing.namespace import nsParse

from zope.location.traversing import RootPhysicallyLocatable # BBB

_marker = object()  # opaque marker that doesn't get security proxied

class DefaultTraversable(object):
    """Traverses objects via attribute and item lookup"""
    zope.interface.implements(ITraversable)

    def __init__(self, subject):
        self._subject = subject

    def traverse(self, name, furtherPath):
        subject = self._subject
        __traceback_info__ = (subject, name, furtherPath)
        attr = getattr(subject, name, _marker)
        if attr is not _marker:
            return attr
        if hasattr(subject, '__getitem__'):
            try:
                return subject[name]
            except (KeyError, TypeError):
                pass
        raise LocationError(subject, name)

class Traverser(object):
    """Provide traverse features"""

    zope.interface.implements(ITraverser)

    # This adapter can be used for any object.

    def __init__(self, wrapper):
        self.context = wrapper

    def traverse(self, path, default=_marker, request=None):
        if not path:
            return self.context

        if isinstance(path, StringTypes):
            path = path.split('/')
            if len(path) > 1 and not path[-1]:
                # Remove trailing slash
                path.pop()
        else:
            path = list(path)

        path.reverse()
        pop = path.pop

        curr = self.context
        if not path[-1]:
            # Start at the root
            pop()
            curr = ILocationInfo(self.context).getRoot()
        try:
            while path:
                name = pop()
                curr = traversePathElement(curr, name, path, request=request)

            return curr
        except LocationError:
            if default == _marker:
                raise
            return default


def traversePathElement(obj, name, further_path, default=_marker,
                        traversable=None, request=None):
    """Traverse a single step 'name' relative to the given object.

    'name' must be a string. '.' and '..' are treated specially, as well as
    names starting with '@' or '+'. Otherwise 'name' will be treated as a
    single path segment.

    'further_path' is a list of names still to be traversed.  This method
    is allowed to change the contents of 'further_path'.

    You can explicitly pass in an ITraversable as the 'traversable'
    argument. If you do not, the given object will be adapted to ITraversable.

    'request' is passed in when traversing from presentation code. This
    allows paths like @@foo to work.

    Raises LocationError if path cannot be found and 'default' was
    not provided.

    """
    __traceback_info__ = (obj, name)

    if name == '.':
        return obj

    if name == '..':
        return obj.__parent__
 
    if name and name[:1] in '@+':
        ns, nm = nsParse(name)
        if ns:
            return namespaceLookup(ns, nm, obj, request)
    else:
        nm = name

    if traversable is None:
        traversable = ITraversable(obj, None)
        if traversable is None:
            raise LocationError('No traversable adapter found', obj)

    try:
        return traversable.traverse(nm, further_path)
    except LocationError:
        if default is not _marker:
            return default
        else:
            raise

    return obj
