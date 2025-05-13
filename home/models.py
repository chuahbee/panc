from django.db import models

from wagtail.models import Page
from wagtail.admin.panels import FieldPanel
# from wagtail.fields import PageChooserBlock
from portfolio.models import P2PIndexPage, CreditCardsIndexPage, CryptoIndexPage


class HomePage(Page):
    p2p_page = models.ForeignKey(P2PIndexPage, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    credit_cards_page = models.ForeignKey(CreditCardsIndexPage, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    crypto_page = models.ForeignKey(CryptoIndexPage, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    content_panels = Page.content_panels + [
        FieldPanel('p2p_page'),
        FieldPanel('credit_cards_page'),
        FieldPanel('crypto_page'),
    ]
