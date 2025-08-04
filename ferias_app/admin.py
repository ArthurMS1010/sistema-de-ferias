from django.contrib import admin
from .models import ServidorFerias, LotacaoAvisoFerias

@admin.register(ServidorFerias)
class ServidorFeriasAdmin(admin.ModelAdmin):
    list_display = ('nome_servidor', 'matricula', 'codigo_lotacao', 'inicio_das_ferias', 'fim_das_ferias', 'competencia')
    list_filter = ('codigo_lotacao', 'competencia')
    search_fields = ('nome_servidor', 'matricula')
    date_hierarchy = 'inicio_das_ferias'

@admin.register(LotacaoAvisoFerias)
class LotacaoAvisoFeriasAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'ativa')
    list_editable = ('ativa',)
    search_fields = ('codigo', 'nome')
