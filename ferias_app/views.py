# ferias_app/views.py

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.management import call_command
import json
import logging
from io import StringIO # Importar StringIO para capturar saída do comando

logger = logging.getLogger(__name__)

@csrf_exempt # Desabilita a proteção CSRF para este endpoint (cuidado em produção!)
def aviso_ferias_endpoint(request):
    """
    Endpoint para ser chamado pelo cronjob do Kubernetes.
    Recebe 'competencia' (YYYY-MM) via POST e dispara a rotina de aviso de férias.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            competencia = data.get('competencia')

            if not competencia:
                logger.error("Parâmetro 'competencia' não fornecido.")
                return JsonResponse({'status': 'error', 'message': 'Parâmetro "competencia" é obrigatório.'}, status=400)

            # Chama o management command para executar a lógica principal
            # Captura a saída do comando para logar ou retornar se necessário
            stdout = StringIO()
            stderr = StringIO()

            # O comando 'importar_ferias' será chamado com o nome do arquivo
            call_command('importar_ferias', competencia=competencia, stdout=stdout, stderr=stderr)
            
            # Verifica se houve erros no comando
            if "ERROR" in stderr.getvalue():
                logger.error(f"Erro na execução do comando: {stderr.getvalue()}")
                return JsonResponse({'status': 'error', 'message': f'Erro na rotina de férias: {stderr.getvalue()}'}, status=500)

            logger.info(f"Rotina de aviso de férias para {competencia} executada com sucesso. Saída: {stdout.getvalue()}")
            return JsonResponse({'status': 'success', 'message': 'Rotina de aviso de férias executada com sucesso.'}, status=200)

        except json.JSONDecodeError:
            logger.error("Corpo da requisição POST inválido (não é um JSON válido).")
            return JsonResponse({'status': 'error', 'message': 'Corpo da requisição deve ser um JSON válido.'}, status=400)
        except Exception as e:
            logger.exception(f"Erro inesperado no endpoint de aviso de férias: {e}")
            return JsonResponse({'status': 'error', 'message': f'Erro interno do servidor: {str(e)}'}, status=500)
    else:
        logger.warning(f"Método {request.method} não permitido para este endpoint.")
        return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)
