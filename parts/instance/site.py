"""Append module search paths for third-party packages to sys.path.

****************************************************************
* This module is automatically imported during initialization. *
****************************************************************

In earlier versions of Python (up to 1.5a3), scripts or modules that
needed to use site-specific modules would place ``import site''
somewhere near the top of their code.  Because of the automatic
import, this is no longer necessary (but code that does it still
works).

This will append site-specific paths to the module search path.  On
Unix (including Mac OSX), it starts with sys.prefix and
sys.exec_prefix (if different) and appends
lib/python<version>/site-packages as well as lib/site-python.
On other platforms (such as Windows), it tries each of the
prefixes directly, as well as with lib/site-packages appended.  The
resulting directories, if they exist, are appended to sys.path, and
also inspected for path configuration files.

A path configuration file is a file whose name has the form
<package>.pth; its contents are additional directories (one per line)
to be added to sys.path.  Non-existing directories (or
non-directories) are never added to sys.path; no directory is added to
sys.path more than once.  Blank lines and lines beginning with
'#' are skipped. Lines starting with 'import' are executed.

For example, suppose sys.prefix and sys.exec_prefix are set to
/usr/local and there is a directory /usr/local/lib/python2.5/site-packages
with three subdirectories, foo, bar and spam, and two path
configuration files, foo.pth and bar.pth.  Assume foo.pth contains the
following:

  # foo package configuration
  foo
  bar
  bletch

and bar.pth contains:

  # bar package configuration
  bar

Then the following directories are added to sys.path, in this order:

  /usr/local/lib/python2.5/site-packages/bar
  /usr/local/lib/python2.5/site-packages/foo

Note that bletch is omitted because it doesn't exist; bar precedes foo
because bar.pth comes alphabetically before foo.pth; and spam is
omitted because it is not mentioned in either path configuration file.

After these path manipulations, an attempt is made to import a module
named sitecustomize, which can perform arbitrary additional
site-specific customizations.  If this import fails with an
ImportError exception, it is silently ignored.

"""

import sys
import os
import __builtin__
import traceback

# Prefixes for site-packages; add additional prefixes like /usr/local here
PREFIXES = [sys.prefix, sys.exec_prefix]
# Enable per user site-packages directory
# set it to False to disable the feature or True to force the feature
ENABLE_USER_SITE = False # buildout does not support user sites.

# for distutils.commands.install
# These values are initialized by the getuserbase() and getusersitepackages()
# functions, through the main() function when Python starts.
USER_SITE = None
USER_BASE = None


def makepath(*paths):
    dir = os.path.join(*paths)
    try:
        dir = os.path.abspath(dir)
    except OSError:
        pass
    return dir, os.path.normcase(dir)


def abs__file__():
    """Set all module' __file__ attribute to an absolute path"""
    for m in sys.modules.values():
        if hasattr(m, '__loader__'):
            continue   # don't mess with a PEP 302-supplied __file__
        try:
            m.__file__ = os.path.abspath(m.__file__)
        except (AttributeError, OSError):
            pass


def removeduppaths():
    """ Remove duplicate entries from sys.path along with making them
    absolute"""
    # This ensures that the initial path provided by the interpreter contains
    # only absolute pathnames, even if we're running from the build directory.
    L = []
    known_paths = set()
    for dir in sys.path:
        # Filter out duplicate paths (on case-insensitive file systems also
        # if they only differ in case); turn relative paths into absolute
        # paths.
        dir, dircase = makepath(dir)
        if not dircase in known_paths:
            L.append(dir)
            known_paths.add(dircase)
    sys.path[:] = L
    return known_paths


def _init_pathinfo():
    """Return a set containing all existing directory entries from sys.path"""
    d = set()
    for dir in sys.path:
        try:
            if os.path.isdir(dir):
                dir, dircase = makepath(dir)
                d.add(dircase)
        except TypeError:
            continue
    return d


def addpackage(sitedir, name, known_paths):
    """Process a .pth file within the site-packages directory:
       For each line in the file, either combine it with sitedir to a path
       and add that to known_paths, or execute it if it starts with 'import '.
    """
    if known_paths is None:
        _init_pathinfo()
        reset = 1
    else:
        reset = 0
    fullname = os.path.join(sitedir, name)
    try:
        f = open(fullname, "rU")
    except IOError:
        return
    with f:
        for n, line in enumerate(f):
            if line.startswith("#"):
                continue
            try:
                if line.startswith(("import ", "import\t")):
                    exec line
                    continue
                line = line.rstrip()
                dir, dircase = makepath(sitedir, line)
                if not dircase in known_paths and os.path.exists(dir):
                    sys.path.append(dir)
                    known_paths.add(dircase)
            except Exception as err:
                print >>sys.stderr, "Error processing line {:d} of {}:\n".format(
                    n+1, fullname)
                for record in traceback.format_exception(*sys.exc_info()):
                    for line in record.splitlines():
                        print >>sys.stderr, '  '+line
                print >>sys.stderr, "\nRemainder of file ignored"
                break
    if reset:
        known_paths = None
    return known_paths


def addsitedir(sitedir, known_paths=None):
    """Add 'sitedir' argument to sys.path if missing and handle .pth files in
    'sitedir'"""
    if known_paths is None:
        known_paths = _init_pathinfo()
        reset = 1
    else:
        reset = 0
    sitedir, sitedircase = makepath(sitedir)
    if not sitedircase in known_paths:
        sys.path.append(sitedir)        # Add path component
    try:
        names = os.listdir(sitedir)
    except os.error:
        return
    dotpth = os.extsep + "pth"
    names = [name for name in names if name.endswith(dotpth)]
    for name in sorted(names):
        addpackage(sitedir, name, known_paths)
    if reset:
        known_paths = None
    return known_paths


def check_enableusersite():
    """Check if user site directory is safe for inclusion

    The function tests for the command line flag (including environment var),
    process uid/gid equal to effective uid/gid.

    None: Disabled for security reasons
    False: Disabled by user (command line option)
    True: Safe and enabled
    """
    if sys.flags.no_user_site:
        return False

    if hasattr(os, "getuid") and hasattr(os, "geteuid"):
        # check process uid == effective uid
        if os.geteuid() != os.getuid():
            return None
    if hasattr(os, "getgid") and hasattr(os, "getegid"):
        # check process gid == effective gid
        if os.getegid() != os.getgid():
            return None

    return True

def getuserbase():
    """Returns the `user base` directory path.

    The `user base` directory can be used to store data. If the global
    variable ``USER_BASE`` is not initialized yet, this function will also set
    it.
    """
    global USER_BASE
    if USER_BASE is not None:
        return USER_BASE
    from sysconfig import get_config_var
    USER_BASE = get_config_var('userbase')
    return USER_BASE

def getusersitepackages():
    """Returns the user-specific site-packages directory path.

    If the global variable ``USER_SITE`` is not initialized yet, this
    function will also set it.
    """
    global USER_SITE
    user_base = getuserbase() # this will also set USER_BASE

    if USER_SITE is not None:
        return USER_SITE

    from sysconfig import get_path
    import os

    if sys.platform == 'darwin':
        from sysconfig import get_config_var
        if get_config_var('PYTHONFRAMEWORK'):
            USER_SITE = get_path('purelib', 'osx_framework_user')
            return USER_SITE

    USER_SITE = get_path('purelib', '%s_user' % os.name)
    return USER_SITE

def addusersitepackages(known_paths):
    """Add a per user site-package to sys.path

    Each user has its own python directory with site-packages in the
    home directory.
    """
    # get the per user site-package path
    # this call will also make sure USER_BASE and USER_SITE are set
    user_site = getusersitepackages()

    if ENABLE_USER_SITE and os.path.isdir(user_site):
        addsitedir(user_site, known_paths)
    return known_paths

def getsitepackages():
    """Returns a list containing all global site-packages directories
    (and possibly site-python).

    For each directory present in the global ``PREFIXES``, this function
    will find its `site-packages` subdirectory depending on the system
    environment, and will return a list of full paths.
    """
    sitepackages = []
    seen = set()

    for prefix in PREFIXES:
        if not prefix or prefix in seen:
            continue
        seen.add(prefix)

        if sys.platform in ('os2emx', 'riscos'):
            sitepackages.append(os.path.join(prefix, "Lib", "site-packages"))
        elif os.sep == '/':
            sitepackages.append(os.path.join(prefix, "lib64",
                                        "python" + sys.version[:3],
                                        "site-packages"))
            sitepackages.append(os.path.join(prefix, "lib",
                                        "python" + sys.version[:3],
                                        "site-packages"))
            sitepackages.append(os.path.join(prefix, "lib", "site-python"))
        else:
            sitepackages.append(prefix)
            sitepackages.append(os.path.join(prefix, "lib64", "site-packages"))
            sitepackages.append(os.path.join(prefix, "lib", "site-packages"))
        if sys.platform == "darwin":
            # for framework builds *only* we add the standard Apple
            # locations.
            from sysconfig import get_config_var
            framework = get_config_var("PYTHONFRAMEWORK")
            if framework:
                sitepackages.append(
                        os.path.join("/Library", framework,
                            sys.version[:3], "site-packages"))
    return sitepackages

def addsitepackages(known_paths):
    """Add site packages, as determined by zc.buildout.

    See original_addsitepackages, below, for the original version."""
    setuptools_path = '/home/raphael/plone2/eggs/setuptools-0.6c11-py2.7.egg'
    sys.path.append(setuptools_path)
    known_paths.add(os.path.normcase(setuptools_path))
    import pkg_resources
    buildout_paths = [
        '/home/raphael/plone2/eggs/Plone-4.3.7-py2.7.egg',
        '/home/raphael/plone2/eggs/Pillow-2.7.0-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/src/raphael.teste/src',
        '/home/raphael/plone2/eggs/ZopeSkel-3.0b3-py2.7.egg',
        '/home/raphael/plone2/eggs/Paste-1.7.5.1-py2.7.egg',
        '/home/raphael/plone2/eggs/setuptools-0.6c11-py2.7.egg',
        '/home/raphael/plone2/eggs/PasteScript-1.7.5-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.recipe.zope2instance-4.2.18-py2.7.egg',
        '/home/raphael/plone2/eggs/ZODB3-3.10.5-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/Zope2-2.13.23-py2.7.egg',
        '/home/raphael/plone2/eggs/zc.recipe.egg-1.3.2-py2.7.egg',
        '/home/raphael/plone2/eggs/mailinglogger-3.7.0-py2.7.egg',
        '/home/raphael/plone2/eggs/zc.buildout-1.7.1-py2.7.egg',
        '/home/raphael/plone2/eggs/PasteDeploy-1.3.4-py2.7.egg',
        '/home/raphael/plone2/eggs/templer.plone-1.0b4-py2.7.egg',
        '/home/raphael/plone2/eggs/templer.zope-1.0b2-py2.7.egg',
        '/home/raphael/plone2/eggs/templer.buildout-1.0b1-py2.7.egg',
        '/home/raphael/plone2/eggs/templer.core-1.0b4-py2.7.egg',
        '/home/raphael/plone2/eggs/wicked-1.1.12-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.theming-1.1.7-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.openid-2.0.4-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.iterate-2.1.13-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.dexterity-2.0.16-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.caching-1.1.10-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFPlone-4.3.7-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFPlacefulWorkflow-1.5.11-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.interface-3.6.7-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/zope.event-3.5.2-py2.7.egg',
        '/home/raphael/plone2/eggs/zdaemon-2.0.7-py2.7.egg',
        '/home/raphael/plone2/eggs/ZConfig-2.9.3-py2.7.egg',
        '/home/raphael/plone2/eggs/zc.lockfile-1.0.2-py2.7.egg',
        '/home/raphael/plone2/eggs/transaction-1.1.1-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.StandardCacheManagers-2.13.1-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.PythonScripts-2.13.2-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.MIMETools-2.13.0-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.MailHost-2.13.2-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.ExternalMethod-2.13.1-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.BTreeFolder2-2.13.3-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.viewlet-3.7.2-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.traversing-3.13.2-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.testing-3.9.7-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.testbrowser-3.11.1-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.tales-3.5.3-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.tal-3.5.2-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.structuredtext-3.5.1-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.size-3.4.1-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.site-3.9.2-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.sequencesort-3.4.0-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.sendmail-3.7.5-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.security-3.7.4-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/zope.schema-4.2.2-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.publisher-3.12.6-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.ptresource-3.9.0-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.proxy-3.6.1-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/zope.processlifetime-1.0-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.pagetemplate-3.6.3-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.location-3.9.1-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.lifecycleevent-3.6.2-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.i18nmessageid-3.5.3-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/zope.i18n-3.7.4-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.exceptions-3.6.2-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.deferredimport-3.5.3-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.contenttype-3.5.5-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.contentprovider-3.7.2-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.container-3.11.2-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/zope.configuration-3.7.4-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.component-3.9.5-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.browserresource-3.10.3-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.browserpage-3.12.2-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.browsermenu-3.9.1-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.browser-1.3-py2.7.egg',
        '/home/raphael/plone2/eggs/zLOG-2.11.2-py2.7.egg',
        '/home/raphael/plone2/eggs/zExceptions-2.13.0-py2.7.egg',
        '/home/raphael/plone2/eggs/tempstorage-2.12.2-py2.7.egg',
        '/home/raphael/plone2/eggs/pytz-2013b-py2.7.egg',
        '/home/raphael/plone2/eggs/initgroups-2.13.0-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/ZopeUndo-2.12.0-py2.7.egg',
        '/home/raphael/plone2/eggs/RestrictedPython-3.6.0-py2.7.egg',
        '/home/raphael/plone2/eggs/Record-2.13.0-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/Products.ZCTextIndex-2.13.5-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/Products.ZCatalog-2.13.27-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.OFSP-2.13.2-py2.7.egg',
        '/home/raphael/plone2/eggs/Persistence-2.13.2-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/MultiMapping-2.13.0-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/Missing-2.13.1-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/ExtensionClass-2.13.2-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/DocumentTemplate-2.13.2-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/DateTime-3.0.3-py2.7.egg',
        '/home/raphael/plone2/eggs/Acquisition-2.13.9-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/AccessControl-3.0.11-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/templer.plone.localcommands-1.0b1-py2.7.egg',
        '/home/raphael/plone2/eggs/five.globalrequest-1.0-py2.7.egg',
        '/home/raphael/plone2/eggs/repoze.xmliter-0.5-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.resourceeditor-1.0-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.resource-1.0.4-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.transformchain-1.0.4-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.subrequest-1.6.9-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.registry-1.2.4-py2.7.egg',
        '/home/raphael/plone2/eggs/lxml-2.3.6-py2.7-linux-x86_64.egg',
        '/home/raphael/plone2/eggs/roman-1.4.0-py2.7.egg',
        '/home/raphael/plone2/eggs/diazo-1.0.6-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.PluggableAuthService-1.10.0-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.PlonePAS-4.1.5-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFCore-2.2.9-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.portlets-2.5.4-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.portlets-2.2-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.openid-2.0.4-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.statusmessages-4.0-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.DCWorkflow-2.2.4-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFEditions-2.2.16-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.Archetypes-1.9.10-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.annotation-3.5.0-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.memoize-1.1.1-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.locking-2.0.8-py2.7.egg',
        '/home/raphael/plone2/eggs/z3c.form-3.2.4-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.GenericSetup-1.7.7-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.z3cform-0.8.1-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.supermodel-1.2.6-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.contentrules-2.0.4-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.autoform-1.6.1-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.z3cform-0.7.7-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.uuid-1.1-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.layout-2.3.13-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.content-2.1.5-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.schemaeditor-1.3.11-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.rfc822-1.1.1-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.namedfile-2.0.9-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.formwidget.namedfile-1.0.13-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.dexterity-2.2.4-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.behavior-1.1-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.textfield-1.2.6-py2.7.egg',
        '/home/raphael/plone2/eggs/collective.z3cform.datetimewidget-1.2.7-py2.7.egg',
        '/home/raphael/plone2/eggs/z3c.zcmlhook-1.0b1-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFDynamicViewFTI-4.1.3-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.registry-1.0.2-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.protect-2.0.2-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.cachepurging-1.0.9-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.caching-1.0.1-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.dottedname-3.4.6-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.deprecation-3.4.1-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.app.locales-3.6.2-py2.7.egg',
        '/home/raphael/plone2/eggs/z3c.autoinclude-0.3.5-py2.7.egg',
        '/home/raphael/plone2/eggs/plonetheme.sunburst-1.4.7-py2.7.egg',
        '/home/raphael/plone2/eggs/plonetheme.classic-1.3.3-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.theme-2.1.5-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.session-3.5.6-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.portlet.static-2.0.4-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.portlet.collection-2.1.8-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.intelligenttext-2.0.3-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.indexer-1.0.3-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.i18n-2.0.10-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.fieldsets-2.0.3-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.browserlayer-2.1.5-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.batching-1.0.5-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.workflow-2.1.9-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.vocabularies-2.1.20-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.viewletmanager-2.0.8-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.users-1.2.2-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.upgrade-1.3.18-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.search-1.1.8-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.redirector-1.2.2-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.locales-4.3.7-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.linkintegrity-1.5.6-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.jquerytools-1.7.0-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.jquery-1.7.2.1-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.i18n-2.0.3-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.form-2.2.6-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.folder-1.1.0-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.discussion-2.2.15-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.customerize-1.2.3-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.controlpanel-2.3.9-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.contentrules-3.0.8-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.contentmenu-2.0.11-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.contentlisting-1.0.5-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.collection-1.0.13-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.blob-1.5.16-py2.7.egg',
        '/home/raphael/plone2/eggs/five.localsitemanager-2.0.5-py2.7.egg',
        '/home/raphael/plone2/eggs/five.customerize-1.1-py2.7.egg',
        '/home/raphael/plone2/eggs/borg.localrole-3.0.2-py2.7.egg',
        '/home/raphael/plone2/eggs/archetypes.referencebrowserwidget-2.5.4-py2.7.egg',
        '/home/raphael/plone2/eggs/archetypes.querywidget-1.1.2-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.TinyMCE-1.3.14-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.ResourceRegistries-2.2.11-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.PortalTransforms-2.1.10-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.PluginRegistry-1.3-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.PloneLanguageTool-3.2.7-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.PlacelessTranslationService-2.0.5-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.PasswordResetTool-2.0.18-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.MimetypesRegistry-2.0.8-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.ExternalEditor-1.1.0-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.ExtendedPathIndex-3.1-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFUid-2.2.1-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFQuickInstallerTool-3.0.12-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFFormController-3.0.5-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFDiffTool-2.1.1-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFDefault-2.2.4-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFCalendar-2.2.3-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.CMFActionIcons-2.1.3-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.ATContentTypes-2.1.16-py2.7.egg',
        '/home/raphael/plone2/eggs/mechanize-0.2.5-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.broken-3.6.0-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.filerepresentation-3.6.1-py2.7.egg',
        '/home/raphael/plone2/eggs/templer.localcommands-1.0b2-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.globalrequest-1.1-py2.7.egg',
        '/home/raphael/plone2/eggs/z3c.caching-2.0a1-py2.7.egg',
        '/home/raphael/plone2/eggs/experimental.cssselect-0.3-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.app.publication-3.12.0-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.ZSQLMethods-2.13.4-py2.7.egg',
        '/home/raphael/plone2/eggs/feedparser-5.0.1-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.formlib-4.3.0-py2.7.egg',
        '/home/raphael/plone2/eggs/five.formlib-1.0.4-py2.7.egg',
        '/home/raphael/plone2/eggs/python_openid-2.2.5-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.ZopeVersionControl-1.1.3-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.copy-3.5.0-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.uuid-1.0.3-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.folder-1.0.7-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.validation-2.0.1-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.Marshall-2.1.4-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.datetime-3.4.1-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.ramcache-1.0-py2.7.egg',
        '/home/raphael/plone2/eggs/six-1.8.0-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.componentvocabulary-1.0.1-py2.7.egg',
        '/home/raphael/plone2/eggs/z3c.formwidget.query-0.11-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.scale-1.3.5-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.synchronize-1.0.1-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.alterego-1.0-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.keyring-3.0.1-py2.7.egg',
        '/home/raphael/plone2/eggs/Unidecode-0.04.1-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.querystring-1.2.7-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.SecureMailHost-1.1.2-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.contentmigration-2.1.11-py2.7.egg',
        '/home/raphael/plone2/eggs/collective.monkeypatcher-1.1.1-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.cachedescriptors-3.5.1-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.stringinterp-1.0.13-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.app.imaging-1.0.11-py2.7.egg',
        '/home/raphael/plone2/eggs/archetypes.schemaextender-2.1.5-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.app.content-3.5.1-py2.7.egg',
        '/home/raphael/plone2/eggs/plone.outputfilters-1.15-py2.7.egg',
        '/home/raphael/plone2/eggs/Markdown-2.0.3-py2.7.egg',
        '/home/raphael/plone2/eggs/python_gettext-1.0-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.app.form-4.0.2-py2.7.egg',
        '/home/raphael/plone2/eggs/Products.ATReferenceBrowserWidget-3.0-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.error-3.7.4-py2.7.egg',
        '/home/raphael/plone2/eggs/zope.authentication-3.7.1-py2.7.egg'
        ]
    for path in buildout_paths:
        sitedir, sitedircase = makepath(path)
        if not sitedircase in known_paths and os.path.exists(sitedir):
            sys.path.append(sitedir)
            known_paths.add(sitedircase)
            pkg_resources.working_set.add_entry(sitedir)
    sys.__egginsert = len(buildout_paths) # Support distribute.
    original_paths = [
        '/usr/lib/python2.7/site-packages/pip-7.1.2-py2.7.egg',
        '/usr/lib/python2.7/site-packages/sc.dev.core-20110707.3-py2.7.egg',
        '/usr/lib/python2.7/site-packages/Sphinx_PyPI_upload-0.2.1-py2.7.egg',
        '/usr/lib/python2.7/site-packages/i18ndude-3.2.2-py2.7.egg',
        '/usr/lib/python2.7/site-packages/rst2pdf-0.16-py2.7.egg',
        '/usr/lib/python2.7/site-packages/Sphinx-1.0.4-py2.7.egg',
        '/usr/lib/python2.7/site-packages/collective.dist-0.2.5-py2.7.egg',
        '/usr/lib/python2.7/site-packages/zest.releaser-3.22-py2.7.egg',
        '/usr/lib/python2.7/site-packages/setuptools_hg-0.2-py2.7.egg',
        '/usr/lib/python2.7/site-packages/setuptools_git-0.3.4-py2.7.egg',
        '/usr/lib/python2.7/site-packages/sc.paster.theme-0.8-py2.7.egg',
        '/usr/lib/python2.7/site-packages/sc.paster.policy-0.7-py2.7.egg',
        '/usr/lib/python2.7/site-packages/sc.paster.buildout-0.7.1-py2.7.egg',
        '/usr/lib/python2.7/site-packages/sc.paster.package-0.8-py2.7.egg',
        '/usr/lib/python2.7/site-packages/ordereddict-1.1-py2.7.egg',
        '/usr/lib/python2.7/site-packages/plone.i18n-3.0.2-py2.7.egg',
        '/usr/lib/python2.7/site-packages/zope.i18nmessageid-4.0.3-py2.7-linux-x86_64.egg',
        '/usr/lib/python2.7/site-packages/zope.interface-4.1.3-py2.7-linux-x86_64.egg',
        '/usr/lib/python2.7/site-packages/zope.tal-4.1.1-py2.7.egg',
        '/usr/lib/python2.7/site-packages/Pygments-2.1-py2.7.egg',
        '/usr/lib/python2.7/site-packages/reportlab-3.2.0-py2.7-linux-x86_64.egg',
        '/usr/lib/python2.7/site-packages/docutils-0.12-py2.7.egg',
        '/usr/lib/python2.7/site-packages/Jinja2-2.8-py2.7.egg',
        '/usr/lib/python2.7/site-packages/Unidecode-0.04.18-py2.7.egg',
        '/usr/lib/python2.7/site-packages/zope.publisher-4.2.2-py2.7.egg',
        '/usr/lib/python2.7/site-packages/zope.i18n-4.1.0-py2.7.egg',
        '/usr/lib/python2.7/site-packages/zope.component-4.2.2-py2.7.egg',
        '/usr/lib/python2.7/site-packages/Cheetah-2.2.1-py2.7-linux-x86_64.egg',
        '/usr/lib/python2.7/site-packages/PasteScript-2.0.2-py2.7.egg',
        '/usr/lib/python2.7/site-packages/PasteDeploy-1.5.2-py2.7.egg',
        '/usr/lib/python2.7/site-packages/Paste-2.0.2-py2.7.egg',
        '/usr/lib64/python2.7/site-packages',
        '/usr/lib64/python2.7/site-packages/gtk-2.0',
        '/usr/lib/python2.7/site-packages'
        ]
    for path in original_paths:
        if path == setuptools_path or path not in known_paths:
            addsitedir(path, known_paths)
    return known_paths

def original_addsitepackages(known_paths):
    """Add site-packages (and possibly site-python) to sys.path"""
    for sitedir in getsitepackages():
        if os.path.isdir(sitedir):
            addsitedir(sitedir, known_paths)

    return known_paths

def setBEGINLIBPATH():
    """The OS/2 EMX port has optional extension modules that do double duty
    as DLLs (and must use the .DLL file extension) for other extensions.
    The library search path needs to be amended so these will be found
    during module import.  Use BEGINLIBPATH so that these are at the start
    of the library search path.

    """
    dllpath = os.path.join(sys.prefix, "Lib", "lib-dynload")
    libpath = os.environ['BEGINLIBPATH'].split(';')
    if libpath[-1]:
        libpath.append(dllpath)
    else:
        libpath[-1] = dllpath
    os.environ['BEGINLIBPATH'] = ';'.join(libpath)


def setquit():
    """Define new builtins 'quit' and 'exit'.

    These are objects which make the interpreter exit when called.
    The repr of each object contains a hint at how it works.

    """
    if os.sep == ':':
        eof = 'Cmd-Q'
    elif os.sep == '\\':
        eof = 'Ctrl-Z plus Return'
    else:
        eof = 'Ctrl-D (i.e. EOF)'

    class Quitter(object):
        def __init__(self, name):
            self.name = name
        def __repr__(self):
            return 'Use %s() or %s to exit' % (self.name, eof)
        def __call__(self, code=None):
            # Shells like IDLE catch the SystemExit, but listen when their
            # stdin wrapper is closed.
            try:
                sys.stdin.close()
            except:
                pass
            raise SystemExit(code)
    __builtin__.quit = Quitter('quit')
    __builtin__.exit = Quitter('exit')


class _Printer(object):
    """interactive prompt objects for printing the license text, a list of
    contributors and the copyright notice."""

    MAXLINES = 23

    def __init__(self, name, data, files=(), dirs=()):
        self.__name = name
        self.__data = data
        self.__files = files
        self.__dirs = dirs
        self.__lines = None

    def __setup(self):
        if self.__lines:
            return
        data = None
        for dir in self.__dirs:
            for filename in self.__files:
                filename = os.path.join(dir, filename)
                try:
                    fp = file(filename, "rU")
                    data = fp.read()
                    fp.close()
                    break
                except IOError:
                    pass
            if data:
                break
        if not data:
            data = self.__data
        self.__lines = data.split('\n')
        self.__linecnt = len(self.__lines)

    def __repr__(self):
        self.__setup()
        if len(self.__lines) <= self.MAXLINES:
            return "\n".join(self.__lines)
        else:
            return "Type %s() to see the full %s text" % ((self.__name,)*2)

    def __call__(self):
        self.__setup()
        prompt = 'Hit Return for more, or q (and Return) to quit: '
        lineno = 0
        while 1:
            try:
                for i in range(lineno, lineno + self.MAXLINES):
                    print self.__lines[i]
            except IndexError:
                break
            else:
                lineno += self.MAXLINES
                key = None
                while key is None:
                    key = raw_input(prompt)
                    if key not in ('', 'q'):
                        key = None
                if key == 'q':
                    break

def setcopyright():
    """Set 'copyright' and 'credits' in __builtin__"""
    __builtin__.copyright = _Printer("copyright", sys.copyright)
    if sys.platform[:4] == 'java':
        __builtin__.credits = _Printer(
            "credits",
            "Jython is maintained by the Jython developers (www.jython.org).")
    else:
        __builtin__.credits = _Printer("credits", """\
    Thanks to CWI, CNRI, BeOpen.com, Zope Corporation and a cast of thousands
    for supporting Python development.  See www.python.org for more information.""")
    here = os.path.dirname(os.__file__)
    __builtin__.license = _Printer(
        "license", "See http://www.python.org/%.3s/license.html" % sys.version,
        ["LICENSE.txt", "LICENSE"],
        [os.path.join(here, os.pardir), here, os.curdir])


class _Helper(object):
    """Define the builtin 'help'.
    This is a wrapper around pydoc.help (with a twist).

    """

    def __repr__(self):
        return "Type help() for interactive help, " \
               "or help(object) for help about object."
    def __call__(self, *args, **kwds):
        import pydoc
        return pydoc.help(*args, **kwds)

def sethelper():
    __builtin__.help = _Helper()

def aliasmbcs():
    """On Windows, some default encodings are not provided by Python,
    while they are always available as "mbcs" in each locale. Make
    them usable by aliasing to "mbcs" in such a case."""
    if sys.platform == 'win32':
        import locale, codecs
        enc = locale.getdefaultlocale()[1]
        if enc.startswith('cp'):            # "cp***" ?
            try:
                codecs.lookup(enc)
            except LookupError:
                import encodings
                encodings._cache[enc] = encodings._unknown
                encodings.aliases.aliases[enc] = 'mbcs'

def setencoding():
    """Set the string encoding used by the Unicode implementation.  The
    default is 'ascii', but if you're willing to experiment, you can
    change this."""
    encoding = "ascii" # Default value set by _PyUnicode_Init()
    if 0:
        # Enable to support locale aware default string encodings.
        import locale
        loc = locale.getdefaultlocale()
        if loc[1]:
            encoding = loc[1]
    if 0:
        # Enable to switch off string to Unicode coercion and implicit
        # Unicode to string conversion.
        encoding = "undefined"
    if encoding != "ascii":
        # On Non-Unicode builds this will raise an AttributeError...
        sys.setdefaultencoding(encoding) # Needs Python Unicode build !


def execsitecustomize():
    """Run custom site specific code, if available."""
    try:
        import sitecustomize
    except ImportError:
        pass
    except Exception:
        if sys.flags.verbose:
            sys.excepthook(*sys.exc_info())
        else:
            print >>sys.stderr, \
                "'import sitecustomize' failed; use -v for traceback"


def execusercustomize():
    """Run custom user specific code, if available."""
    try:
        import usercustomize
    except ImportError:
        pass
    except Exception:
        if sys.flags.verbose:
            sys.excepthook(*sys.exc_info())
        else:
            print>>sys.stderr, \
                "'import usercustomize' failed; use -v for traceback"


def main():
    global ENABLE_USER_SITE

    abs__file__()
    known_paths = removeduppaths()
    from sysconfig import is_python_build
    if is_python_build():
        from _sysconfigdata import build_time_vars
        sys.path.append(os.path.join(build_time_vars['abs_builddir'], 'Modules'))
    if ENABLE_USER_SITE is None:
        ENABLE_USER_SITE = check_enableusersite()
    known_paths = addusersitepackages(known_paths)
    known_paths = addsitepackages(known_paths)
    if sys.platform == 'os2emx':
        setBEGINLIBPATH()
    setquit()
    setcopyright()
    sethelper()
    aliasmbcs()
    setencoding()
    execsitecustomize()
    if ENABLE_USER_SITE:
        execusercustomize()
    # Remove sys.setdefaultencoding() so that users cannot change the
    # encoding after initialization.  The test for presence is needed when
    # this module is run as a script, because this code is executed twice.
    if hasattr(sys, "setdefaultencoding"):
        del sys.setdefaultencoding

main()

def _script():
    help = """\
    %s [--user-base] [--user-site]

    Without arguments print some useful information
    With arguments print the value of USER_BASE and/or USER_SITE separated
    by '%s'.

    Exit codes with --user-base or --user-site:
      0 - user site directory is enabled
      1 - user site directory is disabled by user
      2 - uses site directory is disabled by super user
          or for security reasons
     >2 - unknown error
    """
    args = sys.argv[1:]
    if not args:
        print "sys.path = ["
        for dir in sys.path:
            print "    %r," % (dir,)
        print "]"
        print "USER_BASE: %r (%s)" % (USER_BASE,
            "exists" if os.path.isdir(USER_BASE) else "doesn't exist")
        print "USER_SITE: %r (%s)" % (USER_SITE,
            "exists" if os.path.isdir(USER_SITE) else "doesn't exist")
        print "ENABLE_USER_SITE: %r" %  ENABLE_USER_SITE
        sys.exit(0)

    buffer = []
    if '--user-base' in args:
        buffer.append(USER_BASE)
    if '--user-site' in args:
        buffer.append(USER_SITE)

    if buffer:
        print os.pathsep.join(buffer)
        if ENABLE_USER_SITE:
            sys.exit(0)
        elif ENABLE_USER_SITE is False:
            sys.exit(1)
        elif ENABLE_USER_SITE is None:
            sys.exit(2)
        else:
            sys.exit(3)
    else:
        import textwrap
        print textwrap.dedent(help % (sys.argv[0], os.pathsep))
        sys.exit(10)

if __name__ == '__main__':
    _script()
