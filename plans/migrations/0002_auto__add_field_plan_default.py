# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Plan.default'
        db.add_column('plans_plan', 'default',
                      self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True),
                      keep_default=False)

    def backwards(self, orm):
        # Deleting field 'Plan.default'
        db.delete_column('plans_plan', 'default')

    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'plans.billinginfo': {
            'Meta': {'object_name': 'BillingInfo'},
            'city': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'country': ('plans.model_fields.CountryField', [], {'default': "'PL'", 'max_length': '2'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'street': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'tax_number': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True'}),
            'zipcode': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'plans.invoice': {
            'Meta': {'object_name': 'Invoice'},
            'buyer_city': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'buyer_country': ('plans.model_fields.CountryField', [], {'default': "'PL'", 'max_length': '2'}),
            'buyer_name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'buyer_street': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'buyer_tax_number': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'buyer_zipcode': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'currency': ('django.db.models.fields.CharField', [], {'default': "'EUR'", 'max_length': '3'}),
            'full_number': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'issued': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
            'issued_duplicate': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'issuer_city': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'issuer_country': ('plans.model_fields.CountryField', [], {'default': "'PL'", 'max_length': '2'}),
            'issuer_name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'issuer_street': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'issuer_tax_number': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'issuer_zipcode': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'item_description': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'number': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'order': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['plans.Order']"}),
            'payment_date': ('django.db.models.fields.DateField', [], {}),
            'quantity': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'rebate': ('django.db.models.fields.DecimalField', [], {'default': "'0'", 'max_digits': '4', 'decimal_places': '2'}),
            'require_shipment': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'selling_date': ('django.db.models.fields.DateField', [], {}),
            'shipping_city': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'shipping_country': ('plans.model_fields.CountryField', [], {'default': "'PL'", 'max_length': '2'}),
            'shipping_name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'shipping_street': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'shipping_zipcode': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'tax': ('django.db.models.fields.DecimalField', [], {'db_index': 'True', 'null': 'True', 'max_digits': '4', 'decimal_places': '2', 'blank': 'True'}),
            'tax_total': ('django.db.models.fields.DecimalField', [], {'max_digits': '7', 'decimal_places': '2'}),
            'total': ('django.db.models.fields.DecimalField', [], {'max_digits': '7', 'decimal_places': '2'}),
            'total_net': ('django.db.models.fields.DecimalField', [], {'max_digits': '7', 'decimal_places': '2'}),
            'type': ('django.db.models.fields.IntegerField', [], {'default': '1', 'db_index': 'True'}),
            'unit_price_net': ('django.db.models.fields.DecimalField', [], {'max_digits': '7', 'decimal_places': '2'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'plans.order': {
            'Meta': {'ordering': "('-created',)", 'object_name': 'Order'},
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '7', 'decimal_places': '2', 'db_index': 'True'}),
            'completed': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'currency': ('django.db.models.fields.CharField', [], {'default': "'EUR'", 'max_length': '3'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plan': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'plan_order'", 'to': "orm['plans.Plan']"}),
            'pricing': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['plans.Pricing']"}),
            'tax': ('django.db.models.fields.DecimalField', [], {'db_index': 'True', 'null': 'True', 'max_digits': '4', 'decimal_places': '2', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'plans.plan': {
            'Meta': {'ordering': "('order',)", 'object_name': 'Plan'},
            'available': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'customized': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'default': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_pl': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name_pl': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'order': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'quotas': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['plans.Quota']", 'through': "orm['plans.PlanQuota']", 'symmetrical': 'False'})
        },
        'plans.planpricing': {
            'Meta': {'object_name': 'PlanPricing'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plan': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['plans.Plan']"}),
            'price': ('django.db.models.fields.DecimalField', [], {'max_digits': '7', 'decimal_places': '2', 'db_index': 'True'}),
            'pricing': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['plans.Pricing']"})
        },
        'plans.planquota': {
            'Meta': {'object_name': 'PlanQuota'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plan': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['plans.Plan']"}),
            'quota': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['plans.Quota']"}),
            'value': ('django.db.models.fields.IntegerField', [], {'default': '1', 'null': 'True', 'blank': 'True'})
        },
        'plans.pricing': {
            'Meta': {'ordering': "('period',)", 'object_name': 'Pricing'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name_pl': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'period': ('django.db.models.fields.PositiveIntegerField', [], {'default': '30', 'null': 'True', 'db_index': 'True', 'blank': 'True'})
        },
        'plans.quota': {
            'Meta': {'ordering': "('order',)", 'object_name': 'Quota'},
            'codename': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '50', 'db_index': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_pl': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_boolean': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name_pl': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'order': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'unit_en': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'unit_pl': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'})
        },
        'plans.userplan': {
            'Meta': {'object_name': 'UserPlan'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'expire': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plan': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['plans.Plan']"}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True'})
        }
    }

    complete_apps = ['plans']