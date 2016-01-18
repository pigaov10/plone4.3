from plone.app.testing import PloneSandboxLayer
from plone.app.testing import applyProfile
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting

from plone.testing import z2

from zope.configuration import xmlconfig


class RaphaeltesteLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load ZCML
        import raphael.teste
        xmlconfig.file(
            'configure.zcml',
            raphael.teste,
            context=configurationContext
        )

        # Install products that use an old-style initialize() function
        #z2.installProduct(app, 'Products.PloneFormGen')

#    def tearDownZope(self, app):
#        # Uninstall products installed above
#        z2.uninstallProduct(app, 'Products.PloneFormGen')


RAPHAEL_TESTE_FIXTURE = RaphaeltesteLayer()
RAPHAEL_TESTE_INTEGRATION_TESTING = IntegrationTesting(
    bases=(RAPHAEL_TESTE_FIXTURE,),
    name="RaphaeltesteLayer:Integration"
)
RAPHAEL_TESTE_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(RAPHAEL_TESTE_FIXTURE, z2.ZSERVER_FIXTURE),
    name="RaphaeltesteLayer:Functional"
)
