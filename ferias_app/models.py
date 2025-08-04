# ferias_app/models.py

from django.db import models

class ServidorFerias(models.Model):
    """
    Modelo para armazenar informações de servidores em férias,
    obtidas do endpoint do SARH.
    """
    nome_servidor = models.CharField(max_length=200, verbose_name="Nome do Servidor")
    matricula = models.CharField(max_length=50, unique=True, verbose_name="Matrícula")
    codigo_lotacao = models.CharField(max_length=10, verbose_name="Código da Lotação")
    inicio_das_ferias = models.DateField(verbose_name="Início das Férias")
    fim_das_ferias = models.DateField(verbose_name="Fim das Férias")
    quantidade_dias_ferias = models.IntegerField(verbose_name="Quantidade de Dias")
    # Adicionamos um campo para rastrear a competência para facilitar filtros futuros
    competencia = models.CharField(max_length=7, verbose_name="Competência (YYYY-MM)") 

    class Meta:
        verbose_name = "Servidor em Férias"
        verbose_name_plural = "Servidores em Férias"
        # Garante que não haja duplicatas para a mesma matrícula na mesma competência
        unique_together = ('matricula', 'competencia') 

    def __str__(self):
        return f"{self.nome_servidor} ({self.matricula}) - Férias: {self.inicio_das_ferias} a {self.fim_das_ferias}"

class LotacaoAvisoFerias(models.Model):
    """
    Modelo para armazenar os códigos das lotações que devem receber aviso de férias.
    """
    codigo = models.CharField(max_length=10, unique=True, verbose_name="Código da Lotação")
    nome = models.CharField(max_length=100, verbose_name="Nome da Lotação", blank=True, null=True)
    ativa = models.BooleanField(default=True, verbose_name="Ativa para Aviso")

    class Meta:
        verbose_name = "Lotação para Aviso de Férias"
        verbose_name_plural = "Lotações para Aviso de Férias"

    def __str__(self):
        return f"{self.codigo} - {self.nome or 'Sem Nome'}"
