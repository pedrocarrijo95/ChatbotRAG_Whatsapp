from openai import OpenAI
from dotenv import load_dotenv
import os
from time import sleep
from helpers import *
from flask import Flask, jsonify,render_template, request, Response
import requests

#Inicializamos o Flask
app = Flask(__name__)
app.secret_key = 'pcarrijo'

#Carregamos nossas variaveis de ambiente.
load_dotenv()

#Criamos aqui um objeto OpenAI passando nossa API_KEY coletada no portal de developer da OpenAI.
#Estamos buscando nas variáveis de ambiente neste caso.
cliente = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#Configuramos aqui qual modelo da OpenAI iremos utilizar em nossa aplicacão
modelo = "gpt-3.5-turbo"

#Utilizando o método carrega() do helpers.py estamos carregando um documento txt com dados para nosso RAG.   
contexto = carrega("./dados/dados.txt")

#Vamos aqui criar um método para receber o prompt do usuário (mensagem do usuário) 
def bot(prompt):
    print(prompt)
    maximo_tentativas = 1
    repeticao = 0
    
    #Após recebermos a mensagem do usuário iremos entrar em um loop para definirmos nossa mensagem ao LLM da OpenAI
    while True:
        try:
            #Definimos aqui um "prompt do sistema" passando via variavel o contexto do nosso chatbot que carregamos anteriormente no txt.
            prompt_do_sistema = f"""
            Você é um chatbot de uma empresa de telecomunicao. 
            Você deve gerar respostas utilizando o contexto abaixo.
            
            # Contexto
            {contexto}

            """
            #Montamos aqui nossa mensagem para o LLM, passando o prompt do sistema e prompt do usuario
            response = cliente.chat.completions.create(
                messages=[
                        {
                                "role": "system",
                                "content": prompt_do_sistema
                        },
                        {
                                "role": "user",
                                "content": prompt
                        }
                ],
                #Definimos abaixo os hiperparâmetros do LLM
                temperature=0,
                max_tokens=300,
                top_p=0,
                frequency_penalty=0,
                presence_penalty=0,
                model = modelo)
            #Retornamos a resposta do LLM
            return response
        #Tratamos aqui as exceptions que possam ocorrer
        except Exception as erro:
            repeticao += 1
            if repeticao >= maximo_tentativas:
                    return "Erro no OpenAI: %s" % erro
            print('Erro de comunicação com OpenAI:', erro)
            sleep(1)
        
  

#Whatsapp API
token = os.getenv("TOKEN")
mytoken = os.getenv("MYTOKEN")  
            
#Criamos aqui uma rota de webhook (GET) para servir de validador para nossa API do Whatsapp aceitar como webhook.               
@app.route('/webhook', methods=['GET'])
#Montamos o método de verificacão onde coleta as informacões que a API do Whatsapp envia de verificacão.
def webhook_verification():
    mode = request.args.get('hub.mode')
    challenge = request.args.get('hub.challenge')
    token = request.args.get('hub.verify_token')

    if mode and token:
        #Verifica se o token adicionado na config do Whatsapp é o mesmo do webhook que queremos adicionar.
        if mode == 'subscribe' and token == mytoken:  
            return challenge, 200
        else:
            return '', 403
     
#Agora vamos criar nosso webhook (POST) que é quem recebe a mensagem do Whatsapp e retorna uma resposta.
@app.route("/webhook", methods=["POST"])
def chat():
    try:
        #Coletamos todos os atributos que recebemos no body json.
        body_param = request.json
        
        #Entramos no body json para coletar os campos que recebemos (phone_number_id, from, body, name)
        if 'object' in body_param and \
        'entry' in body_param and \
        body_param['entry'][0]['changes'][0]['value']['messages'][0]:
            #Colocamos os valores recebidos dentro de variáveis
            phon_no_id = body_param['entry'][0]['changes'][0]['value']['metadata']['phone_number_id']
            from_user = body_param['entry'][0]['changes'][0]['value']['messages'][0]['from']
            msg_body = body_param['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            user_name = body_param['entry'][0]['changes'][0]['value']['contacts'][0]['profile']['name']
 
            #Chamamos aqui nosso bot() passando a msg_body que foi a mensagem recebida pelo usuário do Whatsapp.
            #Coletamos o .message.content do nosso bot() que no caso é a resposta do nosso LLM da OpenAI.
            texto_resposta = bot(msg_body).choices[0].message.content
            print("resposta: "+texto_resposta)
            
            #Utilizamos aqui nosso método sendWhatsapp criado abaixo neste código, onde enviamos o número do usuário, o user e a resposta do LLM.
            sendWhatsapp(phon_no_id,from_user, texto_resposta)
            
            
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'error'}), 404
    except Exception as erro:
        return "Erro: %s" % erro


#Aqui é onde criamos nosso sendWhatsapp
def sendWhatsapp(phon_no_id,from_user,texto_resposta):
    #Coletamos aqui o número,user e reposta
    global token
    #Adicionamos na URL de requisicão o número para qual iremos enviar a mensagem e nosso access token coletado na plataforma da Meta Business API.
    url = f"https://graph.facebook.com/v13.0/{phon_no_id}/messages?access_token={token}"

    #Definimos aqui o conteúdo da mensagem e para quem vai a mensagem.
    data = {
        "messaging_product": "whatsapp",
        "to": from_user,
        "text": {
            "body": texto_resposta
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    # Check the response
    try:
        #Acionamos noss request passando as informacões preenchidas acima.
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # Isso levantará uma exceção se houver um erro HTTP
        print("Mensagem enviado com sucesso!")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar mensagem: {e}")
            
        
if __name__ == "__main__":
    app.run(debug = True)