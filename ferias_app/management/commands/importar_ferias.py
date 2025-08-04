# ferias_app/management/commands/importar_ferias.py

from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import requests
import datetime
from collections import defaultdict
import logging
import json # Importar json para tratar a resposta da API

from ferias_app.models import ServidorFerias, LotacaoAvisoFerias

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Importa os dados de férias de servidores e notifica os chefes por e-mail.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--competencia',
            type=str,
            help='Mês/Ano da competência para consulta (formato YYYY-MM). Ex: 2025-08',
            required=True
        )

    def handle(self, *args, **kwargs):
        competencia = kwargs['competencia']
        try:
            ano, mes = map(int, competencia.split('-'))
        except ValueError:
            raise CommandError("Formato de 'competencia' inválido. Use YYYY-MM (ex: 2025-08).")

        self.stdout.write(f"Iniciando rotina de férias para competência: {competencia}")

        # -----------------------------------------------------------
        # ETAPA 1: Consultar servidores em férias
        # -----------------------------------------------------------
        self.stdout.write("1. Consultando servidores em férias no SARH...")
        
        # Obtém os códigos de lotação configurados para aviso
        lotacoes_configuradas = LotacaoAvisoFerias.objects.filter(ativa=True).values_list('codigo', flat=True)
        if not lotacoes_configuradas:
            # Não é um erro fatal se não houver lotações configuradas, apenas encerra a rotina
            self.stdout.write("Nenhuma lotação configurada para aviso de férias na tabela 'LotacaoAvisoFerias'. Encerrando.")
            return

        # Constrói os parâmetros 'codigos' para a URL
        # O endpoint aceita múltiplos 'codigos='
        # Ex: /json/buscarFeriasFuncionarios/2025/08?codigos=10087&codigos=10091
        codigos_param = '&codigos='.join(lotacoes_configuradas)
        
        # Endpoint para buscar funcionários em férias
        # !!! ESTA É UMA URL DE EXEMPLO/PLACEHOLDER. SUBSTITUA PELA URL BASE REAL DO SEU WEBSERVICE SARH !!!
        SARH_FERIAS_ENDPOINT = f"http://exemplo.com/json/buscarFeriasFuncionarios/{ano}/{mes}?codigos={codigos_param}" 
        
        servidores_ferias_api = []
        try:
            response = requests.get(SARH_FERIAS_ENDPOINT)
            response.raise_for_status() # Lança um erro para status de erro (4xx ou 5xx)
            servidores_ferias_api = response.json()
            self.stdout.write(f"  - {len(servidores_ferias_api)} registro s de férias recebidos do SARH.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao acessar o endpoint de férias do SARH: {e}")
            # Não levanta CommandError aqui para permitir que o processo continue para a próxima etapa,
            # mesmo que a consulta de férias falhe, para fins de teste.
            # Em produção, você pode querer levantar o erro.
            self.stdout.write(self.style.WARNING(f"  - ATENÇÃO: Falha na consulta de férias. Verifique a URL do SARH ou a conectividade. Erro: {e}"))
            # Para continuar o fluxo de teste, vamos simular alguns dados se a API falhar
            # REMOVA ISSO EM PRODUÇÃO
            servidores_ferias_api = [
                {'nome_servidor': 'Servidor Teste 1', 'matricula': '12345', 'codigo_lotacao': '10087', 'inicio_das_ferias': '2025-08-01', 'fim_das_ferias': '2025-08-15', 'quantidade_dias_ferias': 15},
                {'nome_servidor': 'Servidor Teste 2', 'matricula': '67890', 'codigo_lotacao': '10087', 'inicio_das_ferias': '2025-08-10', 'fim_das_ferias': '2025-08-20', 'quantidade_dias_ferias': 10},
                {'nome_servidor': 'Servidor Teste 3', 'matricula': '11223', 'codigo_lotacao': '10091', 'inicio_das_ferias': '2025-08-05', 'fim_das_ferias': '2025-08-25', 'quantidade_dias_ferias': 20},
            ]
            self.stdout.write(self.style.WARNING("  - Usando dados simulados para continuar o teste."))

        except json.JSONDecodeError:
            logger.error("Resposta do endpoint de férias do SARH não é um JSON válido.")
            self.stdout.write(self.style.WARNING("  - ATENÇÃO: Resposta do endpoint de férias do SARH não é um JSON válido. Usando dados simulados."))
            # Para continuar o fluxo de teste, vamos simular alguns dados se a API falhar
            # REMOVA ISSO EM PRODUÇÃO
            servidores_ferias_api = [
                {'nome_servidor': 'Servidor Teste 1', 'matricula': '12345', 'codigo_lotacao': '10087', 'inicio_das_ferias': '2025-08-01', 'fim_das_ferias': '2025-08-15', 'quantidade_dias_ferias': 15},
                {'nome_servidor': 'Servidor Teste 2', 'matricula': '67890', 'codigo_lotacao': '10087', 'inicio_das_ferias': '2025-08-10', 'fim_das_ferias': '2025-08-20', 'quantidade_dias_ferias': 10},
                {'nome_servidor': 'Servidor Teste 3', 'matricula': '11223', 'codigo_lotacao': '10091', 'inicio_das_ferias': '2025-08-05', 'fim_das_ferias': '2025-08-25', 'quantidade_dias_ferias': 20},
            ]
            self.stdout.write(self.style.WARNING("  - Usando dados simulados para continuar o teste."))


        # Limpa dados antigos para a competência atual antes de importar novos
        ServidorFerias.objects.filter(competencia=competencia).delete()
        self.stdout.write(f"  - Dados de férias antigos para {competencia} removidos.")

        # Salva/atualiza os dados no banco de dados local
        servidores_importados_count = 0
        lotacoes_com_ferias = set() # Para coletar as lotações que realmente têm férias neste mês
        for item in servidores_ferias_api:
            try:
                # Validação e conversão de datas
                # Assumindo que as chaves no JSON da API são 'inicio_das_ferias' e 'fim_das_ferias'
                # E 'quantidade_dias_ferias'
                inicio_ferias_date = datetime.datetime.strptime(item.get('inicio_das_ferias'), '%Y-%m-%d').date()
                fim_ferias_date = datetime.datetime.strptime(item.get('fim_das_ferias'), '%Y-%m-%d').date()

                servidor, created = ServidorFerias.objects.update_or_create(
                    matricula=item.get('matricula'),
                    competencia=competencia, # Usamos a competência para o unique_together
                    defaults={
                        'nome_servidor': item.get('nome_servidor'),
                        'codigo_lotacao': item.get('codigo_lotacao'),
                        'inicio_das_ferias': inicio_ferias_date,
                        'fim_das_ferias': fim_ferias_date,
                        'quantidade_dias_ferias': item.get('quantidade_dias_ferias') # Assumindo a chave no JSON
                    }
                )
                lotacoes_com_ferias.add(item.get('codigo_lotacao'))
                servidores_importados_count += 1
            except (ValueError, TypeError) as e:
                logger.warning(f"  - Erro ao processar item de férias (formato de data/dias inválido): {item} - {e}")
            except Exception as e:
                logger.error(f"  - Erro ao salvar servidor de férias {item.get('matricula')}: {e}")
        
        self.stdout.write(f"  - {servidores_importados_count} servidores de férias importados/atualizados.")

        if not lotacoes_com_ferias:
            self.stdout.write("Nenhum servidor em férias encontrado para as lotações configuradas nesta competência. Encerrando.")
            return

        # -----------------------------------------------------------
        # ETAPA 2: Consultar chefes das lotações com servidores em férias
        # -----------------------------------------------------------
        self.stdout.write("2. Consultando chefes das lotações no SARH...")
        
        # Constrói os parâmetros 'codigos' para a URL de chefia
        codigos_lotacoes_chefia_param = '&codigos='.join(lotacoes_com_ferias)
        
        # Endpoint para buscar lotações com chefia
        # !!! ESTA É UMA URL DE EXEMPLO/PLACEHOLDER. SUBSTITUA PELA URL BASE REAL DO SEU WEBSERVICE SARH !!!
        SARH_CHEFIA_ENDPOINT = f"http://exemplo.com/json/buscarLotacoesComChefia?codigos={codigos_lotacoes_chefia_param}"
        
        chefes_por_lotacao = {} # {codigo_lotacao: {nome_chefe: '...', email_chefe: '...'}}
        try:
            response = requests.get(SARH_CHEFIA_ENDPOINT)
            response.raise_for_status()
            dados_chefia = response.json()
            
            for item in dados_chefia:
                # Assumindo que a resposta da API de chefia tem 'codigo_lotacao', 'nome_chefe', 'email_chefe'
                chefes_por_lotacao[item.get('codigo_lotacao')] = {
                    'nome_chefe': item.get('nome_chefe', 'Chefe da Lotação'),
                    'email_chefe': item.get('email_chefe')
                }
            self.stdout.write(f"  - Informações de chefia para {len(chefes_por_lotacao)} lotações recebidas.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao acessar o endpoint de chefia do SARH: {e}")
            self.stdout.write(self.style.WARNING(f"  - ATENÇÃO: Falha na consulta de chefia. Verifique a URL do SARH ou a conectividade. Erro: {e}"))
            # Para continuar o fluxo de teste, vamos simular alguns dados se a API falhar
            # REMOVA ISSO EM PRODUÇÃO
            for codigo in lotacoes_com_ferias:
                chefes_por_lotacao[codigo] = {
                    'nome_chefe': f'Chefe da Lotação {codigo}',
                    'email_chefe': f'chefe.{codigo}@exemplo.com' # Use um email real para testar o envio
                }
            self.stdout.write(self.style.WARNING("  - Usando dados simulados para chefia para continuar o teste."))
        except json.JSONDecodeError:
            logger.error("Resposta do endpoint de chefia do SARH não é um JSON válido.")
            self.stdout.write(self.style.WARNING("  - ATENÇÃO: Resposta do endpoint de chefia do SARH não é um JSON válido. Usando dados simulados."))
            # Para continuar o fluxo de teste, vamos simular alguns dados se a API falhar
            # REMOVA ISSO EM PRODUÇÃO
            for codigo in lotacoes_com_ferias:
                chefes_por_lotacao[codigo] = {
                    'nome_chefe': f'Chefe da Lotação {codigo}',
                    'email_chefe': f'chefe.{codigo}@exemplo.com' # Use um email real para testar o envio
                }
            self.stdout.write(self.style.WARNING("  - Usando dados simulados para chefia para continuar o teste."))


        # -----------------------------------------------------------
        # ETAPA 3: Montar e enviar e-mails
        # -----------------------------------------------------------
        self.stdout.write("3. Montando e enviando e-mails de aviso de férias...")
        
        # Agrupa os servidores por lotação para enviar um e-mail por chefe
        servidores_por_lotacao = defaultdict(list)
        for servidor in ServidorFerias.objects.filter(competencia=competencia, codigo_lotacao__in=lotacoes_com_ferias):
            servidores_por_lotacao[servidor.codigo_lotacao].append(servidor)

        emails_enviados_count = 0
        for codigo_lotacao, servidores in servidores_por_lotacao.items():
            chefe_info = chefes_por_lotacao.get(codigo_lotacao)
            
            if chefe_info and chefe_info.get('email_chefe'):
                email_chefe = chefe_info['email_chefe']
                nome_chefe = chefe_info['nome_chefe']

                context = {
                    'nome_chefe': nome_chefe,
                    'codigo_lotacao': codigo_lotacao,
                    'competencia': competencia,
                    'servidores': servidores,
                }
                
                # Renderiza o template HTML do e-mail
                html_message = render_to_string('ferias_app/email_aviso_ferias.html', context)
                
                subject = f"Aviso de Férias para Lotação {codigo_lotacao} - Competência {competencia}"
                
                try:
                    email = EmailMessage(
                        subject,
                        html_message,
                        settings.DEFAULT_FROM_EMAIL, # Remetente configurado em settings.py
                        [email_chefe], # Destinatário
                    )
                    email.content_subtype = "html" # Define o tipo de conteúdo como HTML
                    email.send()
                    emails_enviados_count += 1
                    self.stdout.write(f"  - E-mail enviado para {nome_chefe} ({email_chefe}) da lotação {codigo_lotacao}.")
                except Exception as e:
                    logger.error(f"  - Erro ao enviar e-mail para {email_chefe} da lotação {codigo_lotacao}: {e}")
            else:
                logger.warning(f"  - Não foi possível enviar e-mail para a lotação {codigo_lotacao}: Chefe ou e-mail não encontrados.")

        self.stdout.write(self.style.SUCCESS(f"Rotina concluída! {emails_enviados_count} e-mails de aviso de férias enviados."))
