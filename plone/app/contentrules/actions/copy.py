from OFS.SimpleItem import SimpleItem
from persistent import Persistent 

from zope.interface import implements, Interface
from zope.component import adapts
from zope.formlib import form
from zope import schema

from plone.contentrules.rule.interfaces import IExecutable, IRuleElementData

from plone.app.contentrules.browser.formhelper import AddForm, EditForm
from plone.app.vocabularies.catalog import SearchableTextSourceBinder
from plone.app.form.widgets.uberselectionwidget import UberSelectionWidget

import transaction
from Acquisition import aq_inner, aq_parent
from ZODB.POSException import ConflictError
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone import PloneMessageFactory as _

from Products.CMFPlone import utils
from Products.statusmessages.interfaces import IStatusMessage

class ICopyAction(Interface):
    """Interface for the configurable aspects of a move action.
    
    This is also used to create add and edit forms, below.
    """
    
    target_folder = schema.Choice(title=_(u"Target folder"),
                                  description=_(u"As a path relative to the portal root."),
                                  required=True,
                                  source=SearchableTextSourceBinder({'is_folderish' : True}))
         
class CopyAction(SimpleItem):
    """The actual persistent implementation of the action element.
    """
    implements(ICopyAction, IRuleElementData)
    
    target_folder = ''
    element = 'plone.actions.Copy'
    
    @property
    def summary(self):
        return _(u"Copy to folder ${folder}.",
                 mapping=dict(folder=self.target_folder))
    
class CopyActionExecutor(object):
    """The executor for this action.
    """
    implements(IExecutable)
    adapts(Interface, ICopyAction, Interface)
         
    def __init__(self, context, element, event):
        self.context = context
        self.element = element
        self.event = event

    def __call__(self):
        portal_url = getToolByName(self.context, 'portal_url', None)
        if portal_url is None:
            return False
        
        obj = self.event.object
        parent = aq_parent(aq_inner(obj))
        
        path = self.element.target_folder
        if len(path) > 1 and path[0] == '/':
            path = path[1:]
        target = portal_url.getPortalObject().unrestrictedTraverse(str(path), None)
    
        if target is None:
            self.error(obj, _(u"Target folder ${target} does not exist", mapping={'target' : path}))
            return False
        
        transaction.savepoint()
        
        try:
            cpy = parent.manage_copyObjects((obj.getId(),))
        except ConflictError, e:
            raise e
        except Exception, e:
            self.error(obj, str(e))
            return False
            
        transaction.savepoint()
        
        try:
            target.manage_pasteObjects(cpy)
        except ConflictError, e:
            raise e
        except Exception, e:
            self.error(obj, str(e))
            return False
        
        return True 
        
    def error(self, obj, error):
        request = getattr(self.context, 'REQUEST', None)
        if request is not None:
            title = utils.pretty_title_or_id(obj, obj)
            message = _(u"Unable to copy ${name} as part of content rule 'copy' action: ${error}",
                          mapping={'name' : title, 'error' : error})
            IStatusMessage(request).addStatusMessage(message, type="error")
        
class CopyAddForm(AddForm):
    """An add form for move-to-folder actions.
    """
    form_fields = form.FormFields(ICopyAction)
    form_fields['target_folder'].custom_widget = UberSelectionWidget
    label = _(u"Add Copy Action")
    description = _(u"A copy action can copy an object to a different folder.")
    form_name = _(u"Configure element")
    
    def create(self, data):
        a = CopyAction()
        form.applyChanges(a, self.form_fields, data)
        return a

class CopyEditForm(EditForm):
    """An edit form for copy rule actions.
    
    Formlib does all the magic here.
    """
    form_fields = form.FormFields(ICopyAction)
    form_fields['target_folder'].custom_widget = UberSelectionWidget
    label = _(u"Edit Copy Action")
    description = _(u"A copy action can copy an object to a different folder.")
    form_name = _(u"Configure element")
