# -*- coding: utf-8 -*-
from doctest import DocTestSuite
from zope.component.testing import setUp
from zope.component.testing import tearDown
from zope.configuration.xmlconfig import XMLConfig
from zope.site import hooks

import doctest
import unittest
import zope.component


def vocabSetUp(self):
    setUp()
    import plone.app.vocabularies
    XMLConfig('meta.zcml', zope.component)()
    XMLConfig('configure.zcml', plone.app.vocabularies)()
    hooks.setHooks()


def vocabTearDown(self):
    tearDown()
    hooks.resetHooks()
    hooks.setSite()


def test_suite():
    optionflags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
    return unittest.TestSuite(
        (
            DocTestSuite(
                'plone.app.vocabularies.terms'
            ),
            DocTestSuite(
                'plone.app.vocabularies.catalog',
                setUp=vocabSetUp,
                tearDown=vocabTearDown,
                optionflags=optionflags
            ),
            DocTestSuite(
                'plone.app.vocabularies.datetimerelated',
                setUp=vocabSetUp,
                tearDown=vocabTearDown,
                optionflags=optionflags
            ),
            DocTestSuite(
                'plone.app.vocabularies.editors',
                setUp=vocabSetUp,
                tearDown=vocabTearDown,
                optionflags=optionflags
            ),
            DocTestSuite(
                'plone.app.vocabularies.groups',
                setUp=vocabSetUp,
                tearDown=vocabTearDown,
                optionflags=optionflags
            ),
            DocTestSuite(
                'plone.app.vocabularies.language',
                setUp=vocabSetUp,
                tearDown=vocabTearDown,
                optionflags=optionflags
            ),
            DocTestSuite(
                'plone.app.vocabularies.security',
                setUp=vocabSetUp,
                tearDown=vocabTearDown,
                optionflags=optionflags
            ),
            DocTestSuite(
                'plone.app.vocabularies.skins',
                setUp=vocabSetUp,
                tearDown=vocabTearDown,
                optionflags=optionflags
            ),
            DocTestSuite(
                'plone.app.vocabularies.types',
                setUp=vocabSetUp,
                tearDown=vocabTearDown,
                optionflags=optionflags
            ),
            DocTestSuite(
                'plone.app.vocabularies.users',
                setUp=vocabSetUp,
                tearDown=vocabTearDown,
                optionflags=optionflags
            ),
            DocTestSuite(
                'plone.app.vocabularies.workflow',
                setUp=vocabSetUp,
                tearDown=vocabTearDown,
                optionflags=optionflags
            ),
        )
    )

