import sys
import os
import cv2
import re
import json
import shutil
import sqlite3
import time
import numpy as np
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QMessageBox, QFrame, QStackedWidget, QListWidget, 
                             QListWidgetItem, QComboBox, QDialog, QGridLayout)
from PyQt6.QtGui import QImage, QPixmap, QFont
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QPropertyAnimation, QRect

# Tenta carregar a biblioteca de comunicação serial de forma opcional
try:
    import serial
    import serial.tools.list_ports
    SERIAL_DISPONIVEL = True
except ImportError:
    SERIAL_DISPONIVEL = False

# ==============================================================================
# FUNÇÕES DE COMUNICAÇÃO COM O BANCO DE DADOS (SQLITE)
# ==============================================================================
def obter_senha_banco():
    """Busca a senha do administrador gravada no banco de dados SQLite."""
    try:
        conexao = sqlite3.connect("historico.db")
        cursor = conexao.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'senha_admin'")
        resultado = cursor.fetchone()
        conexao.close()
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao ler banco de dados: {e}")
        return None

def salvar_senha_banco(senha):
    """Salva ou atualiza a senha de administrador no banco SQLite."""
    try:
        conexao = sqlite3.connect("historico.db")
        cursor = conexao.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        cursor.execute("INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES ('senha_admin', ?)", (senha,))
        conexao.commit()
        conexao.close()
    except Exception as e:
        print(f"Erro ao gravar senha no banco: {e}")


# ==============================================================================
# CLASSE DO TECLADO VIRTUAL ALFANUMÉRICO (MODAL)
# ==============================================================================
class TecladoVirtualDialog(QDialog):
    def __init__(self, parent=None, titulo="Digite", texto_inicial="", is_password=False):
        super().__init__(parent)
        self.texto_retorno = texto_inicial
        self.is_password = is_password
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(400, 480)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a24;
                border: 2px solid #4b6584;
                border-radius: 16px;
            }
            QLabel {
                color: #a5b1c2;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #262630;
                border: 1px solid #4b6584;
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #262630;
                color: #ffffff;
                border: 1px solid #4b6584;
                border-radius: 8px;
                font-size: 16px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                min-height: 42px;
            }
            QPushButton:hover {
                background-color: #4b6584;
            }
            QPushButton:pressed {
                background-color: #2f3542;
            }
            #btn_backspace, #btn_limpar {
                background-color: #3d2d2d;
                border: 1px solid #8c2d2d;
            }
            #btn_backspace:hover, #btn_limpar:hover {
                background-color: #8c2d2d;
            }
            #btn_confirmar {
                background-color: #2d503d;
                border: 1px solid #2ecc71;
            }
            #btn_confirmar:hover {
                background-color: #2ecc71;
            }
            #btn_cancelar {
                background-color: transparent;
                border: 1px solid #8c2d2d;
            }
            #btn_cancelar:hover {
                background-color: #8c2d2d;
            }
        """)
        
        self.inicializar_ui(titulo)

    def inicializar_ui(self, titulo):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        lbl_titulo = QLabel(titulo.upper())
        lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_titulo)
        
        # Campo de visualização de texto digitado
        self.display = QLineEdit()
        self.display.setText(self.texto_retorno)
        self.display.setReadOnly(True)
        if self.is_password:
            self.display.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.display)
        
        grid_teclas = QGridLayout()
        grid_teclas.setSpacing(6)
        
        # Definição das linhas do teclado virtual
        linhas = [
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
            ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
            ["A", "S", "D", "F", "G", "H", "J", "K", "L", "-"],
            ["Z", "X", "C", "V", "B", "N", "M", "_", ".", "⌫"]
        ]
        
        for num_linha, caracteres in enumerate(linhas):
            for num_coluna, caractere in enumerate(caracteres):
                btn = QPushButton(caractere)
                
                if caractere == "⌫":
                    btn.setObjectName("btn_backspace")
                    btn.clicked.connect(self.pressionar_backspace)
                else:
                    btn.clicked.connect(lambda checked, char=caractere: self.pressionar_letra(char))
                
                grid_teclas.addWidget(btn, num_linha, num_coluna)
        
        layout.addLayout(grid_teclas)
        
        # Controles inferiores (Espaço, Limpar, Confirmar, Cancelar)
        layout_acoes = QHBoxLayout()
        layout_acoes.setSpacing(8)
        
        btn_limpar = QPushButton("Limpar")
        btn_limpar.setObjectName("btn_limpar")
        btn_limpar.clicked.connect(self.limpar_texto)
        layout_acoes.addWidget(btn_limpar)
        
        btn_espaco = QPushButton("Espaço")
        btn_espaco.clicked.connect(lambda: self.pressionar_letra(" "))
        layout_acoes.addWidget(btn_espaco)
        
        layout.addLayout(layout_acoes)
        
        layout_botoes_finais = QHBoxLayout()
        layout_botoes_finais.setSpacing(8)
        
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar")
        btn_cancelar.clicked.connect(self.reject)
        layout_botoes_finais.addWidget(btn_cancelar)
        
        btn_confirmar = QPushButton("Confirmar ✔")
        btn_confirmar.setObjectName("btn_confirmar")
        btn_confirmar.clicked.connect(self.confirmar_texto)
        layout_botoes_finais.addWidget(btn_confirmar)
        
        layout.addLayout(layout_botoes_finais)

    def pressionar_letra(self, letra):
        self.texto_retorno += letra
        self.display.setText(self.texto_retorno)

    def pressionar_backspace(self):
        self.texto_retorno = self.texto_retorno[:-1]
        self.display.setText(self.texto_retorno)

    def limpar_texto(self):
        self.texto_retorno = ""
        self.display.clear()

    def confirmar_texto(self):
        self.accept()

    def obter_texto(self):
        return self.texto_retorno


# ==============================================================================
# ENTRADA DE TEXTO ADAPTADA PARA TOQUE (AUTOMATICAMENTE ABRE O TECLADO VIRTUAL)
# ==============================================================================
class TouchLineEdit(QLineEdit):
    def __init__(self, parent=None, placeholder="", is_password=False):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.is_password = is_password
        if is_password:
            self.setEchoMode(QLineEdit.EchoMode.Password)
            
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        # Invoca o teclado virtual trazendo o texto que já está no input
        dialog = TecladoVirtualDialog(
            self.parent(), 
            titulo=self.placeholderText(), 
            texto_inicial=self.text(), 
            is_password=self.is_password
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.setText(dialog.obter_texto())


# ==============================================================================
# CLASSE DO DIALOG DE AUTENTICAÇÃO / CADASTRO DE SENHA DE ADMIN
# ==============================================================================
class AdminAuthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.autenticado = False
        self.senha_salva = obter_senha_banco()
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(360, 320)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #262630;
                border: 2px solid #4b6584;
                border-radius: 12px;
            }
            QLabel {
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton {
                background-color: #4b6584;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #57606f;
            }
            #btn_cancelar {
                background-color: transparent;
                border: 1px solid #8c2d2d;
                color: #ffffff;
            }
            #btn_cancelar:hover {
                background-color: #8c2d2d;
            }
        """)
        
        self.inicializar_ui()

    def inicializar_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        lbl_cadeado = QLabel("🔒" if self.senha_salva else "🆕")
        lbl_cadeado.setFont(QFont("Segoe UI", 32))
        lbl_cadeado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_cadeado)

        self.lbl_titulo = QLabel("ACESSO RESTRITO" if self.senha_salva else "PRIMEIRO ACESSO")
        self.lbl_titulo.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_titulo)

        # Descrição dinâmica orientando o usuário
        self.lbl_desc = QLabel(
            "Toque abaixo para digitar a Senha de Admin" if self.senha_salva 
            else "Nenhuma senha cadastrada!\nToque abaixo para criar sua Senha Master."
        )
        self.lbl_desc.setFont(QFont("Segoe UI", 9))
        self.lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_desc.setStyleSheet("color: #a5b1c2;")
        layout.addWidget(self.lbl_desc)

        # Input de toque virtualizado
        self.input_senha = TouchLineEdit(
            self, 
            placeholder="Nova Senha de Admin" if not self.senha_salva else "Senha de Admin", 
            is_password=True
        )
        self.input_senha.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.input_senha)

        layout_botoes = QHBoxLayout()
        layout_botoes.setSpacing(10)

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btn_cancelar")
        btn_cancelar.clicked.connect(self.reject)
        layout_botoes.addWidget(btn_cancelar)

        btn_entrar = QPushButton("Salvar" if not self.senha_salva else "Entrar")
        btn_entrar.clicked.connect(self.processar_acao)
        layout_botoes.addWidget(btn_entrar)

        layout.addLayout(layout_botoes)

    def processar_acao(self):
        senha_digitada = self.input_senha.text().strip()
        
        if not senha_digitada:
            QMessageBox.warning(self, "Aviso", "O campo de senha não pode estar vazio!")
            return

        if not self.senha_salva:
            # Fluxo de criação de senha (Primeiro Acesso)
            salvar_senha_banco(senha_digitada)
            self.senha_salva = senha_digitada
            self.autenticado = True
            QMessageBox.information(self, "Sucesso", "Senha de administrador cadastrada com sucesso!")
            self.accept()
        else:
            # Fluxo comum de verificação de login
            if senha_digitada == self.senha_salva:
                self.autenticado = True
                self.accept()
            else:
                QMessageBox.critical(self, "Acesso Negado", "A senha digitada está incorreta!")
                self.input_senha.clear()


# ==============================================================================
# THREAD DA CÂMERA: Captura, recorta e realiza detecção de rostos com HUD
# ==============================================================================
class CameraThread(QThread):
    frame_signal = pyqtSignal(QImage, object)
    reconhecido_signal = pyqtSignal(str)

    def __init__(self, camera_index=0):
        super().__init__()
        self.executando = True
        self.modo = "reconhecimento"
        self.camera_index = camera_index
        
        self.detector_rosto = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        self.reconhecedor = None
        self.labels_map = {}
        self.carregar_modelo()

        # Controle de exibição estável do HUD (evita oscilação rápida)
        self.status_travado = None          # Pode ser "LIBERADO" ou "NEGADO"
        self.nome_travado = ""              # Nome do usuário liberado
        self.timestamp_trava = 0.0          # Timestamp de quando iniciou o congelamento
        self.tempo_trava_liberado = 6.0     # Tempo (segundos) que o banner de LIBERADO fica travado
        self.tempo_trava_negado = 2.0       # Tempo (segundos) que o banner de NEGADO fica travado

    def carregar_modelo(self):
        """Carrega o modelo treinado de inteligência LBPH."""
        if os.path.exists("classificador_lbph.yml") and os.path.exists("labels.json"):
            try:
                self.reconhecedor = cv2.face.LBPHFaceRecognizer_create()
                self.reconhecedor.read("classificador_lbph.yml")
                
                with open("labels.json", "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    self.labels_map = {int(k): v for k, v in dados.items()}
                print("Modelo de Reconhecimento Facial carregado com sucesso!")
            except Exception as e:
                print(f"Erro ao carregar o modelo de inteligência: {e}")
                self.reconhecedor = None
        else:
            self.reconhecedor = None

    def desenhar_banner_status(self, frame, texto, cor_bgr):
        """Desenha um banner de status sólido no topo do frame com texto centralizado."""
        largura = frame.shape[1]
        
        # Coordenadas do banner no topo da imagem
        ponto_inicial = (15, 15)
        ponto_final = (largura - 15, 115)
        
        # Desenha o retângulo de fundo do banner (sólido)
        cv2.rectangle(frame, ponto_inicial, ponto_final, cor_bgr, -1)
        # Borda fina branca para acabamento
        cv2.rectangle(frame, ponto_inicial, ponto_final, (255, 255, 255), 1)
        
        # Configuração do Texto
        fonte = cv2.FONT_HERSHEY_SIMPLEX
        escala = 0.65
        espessura = 2
        
        tamanho_texto, _ = cv2.getTextSize(texto, fonte, escala, espessura)
        texto_x = (largura - tamanho_texto[0]) // 2
        texto_y = 65 + (tamanho_texto[1] // 2)
        
        cv2.putText(frame, texto, (texto_x, texto_y), fonte, escala, (255, 255, 255), espessura, cv2.LINE_AA)

    def run(self):
        webcam = cv2.VideoCapture(self.camera_index)
        
        while self.executando:
            sucesso, frame = webcam.read()
            if sucesso:
                tempo_atual = time.time()
                
                # 1. Gerenciamento de estabilidade visual (Máquina de estados temporal)
                visual_esta_travado = False
                if self.status_travado is not None:
                    tempo_decorrido = tempo_atual - self.timestamp_trava
                    limite_trava = self.tempo_trava_liberado if self.status_travado == "LIBERADO" else self.tempo_trava_negado
                    
                    if tempo_decorrido < limite_trava:
                        visual_esta_travado = True
                    else:
                        self.status_travado = None
                        self.nome_travado = ""

                altura_original, largura_original = frame.shape[:2]
                largura_9_16 = int(altura_original * 9 / 16)
                x_inicio = (largura_original - largura_9_16) // 2
                
                frame_recortado = frame[:, x_inicio:x_inicio + largura_9_16]
                frame_limpo = frame_recortado.copy()
                
                frame_cinza = cv2.cvtColor(frame_recortado, cv2.COLOR_BGR2GRAY)
                rostos = self.detector_rosto.detectMultiScale(
                    frame_cinza, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
                )

                status_atual = "MONITORANDO"
                nome_identificado = ""

                # Se o estado do visual estiver congelado de uma detecção recente, herda o status
                if visual_esta_travado:
                    status_atual = self.status_travado
                    nome_identificado = self.nome_travado

                for (x, y, largura, altura) in rostos:
                    if visual_esta_travado:
                        # Rastreia o rosto fisicamente mantendo a cor de feedback do banner atual
                        if status_atual == "LIBERADO":
                            cor_retangulo = (46, 204, 113) # Verde Esmeralda (BGR)
                        else:
                            cor_retangulo = (0, 0, 230) # Vermelho Puro (BGR)
                    else:
                        # Cor Padrão: Cinza-azul do tema para busca silenciosa
                        cor_retangulo = (132, 101, 75)
                        
                        if self.modo == "reconhecimento" and self.reconhecedor is not None:
                            rosto_cinza = frame_cinza[y:y+altura, x:x+largura]
                            try:
                                id_previsto, confianca = self.reconhecedor.predict(rosto_cinza)
                                
                                # Limiar seguro do classificador LBPH (< 55 significa alta precisão)
                                if confianca < 55:
                                    nome_usuario = self.labels_map.get(id_previsto, "Desconhecido")
                                    nome_identificado = nome_usuario.replace('_', ' ').upper()
                                    
                                    # Ativa o congelamento de exibição do status "LIBERADO"
                                    self.status_travado = "LIBERADO"
                                    self.nome_travado = nome_identificado
                                    self.timestamp_trava = tempo_atual
                                    visual_esta_travado = True
                                    
                                    status_atual = "LIBERADO"
                                    cor_retangulo = (46, 204, 113) # Verde
                                    
                                    # Emite o sinal para gravar no banco e enviar comando ao Arduino
                                    self.reconhecido_signal.emit(nome_usuario)
                                else:
                                    # Ativa o congelamento de exibição do status "NEGADO"
                                    self.status_travado = "NEGADO"
                                    self.nome_travado = ""
                                    self.timestamp_trava = tempo_atual
                                    visual_esta_travado = True
                                    
                                    status_atual = "NEGADO"
                                    cor_retangulo = (0, 0, 230) # Vermelho
                            except Exception as e:
                                print(f"Erro ao analisar face: {e}")
                        elif self.modo == "cadastro":
                            cor_retangulo = (132, 101, 75)

                    # Desenha o retângulo ao redor do rosto
                    cv2.rectangle(frame_recortado, (x, y), (x + largura, y + altura), cor_retangulo, 2)

                # Se estiver em modo de reconhecimento, exibe os banners na tela
                if self.modo == "reconhecimento":
                    if status_atual == "LIBERADO":
                        self.desenhar_banner_status(frame_recortado, f"LIBERADO - {nome_identificado}", (46, 204, 113))
                    elif status_atual == "NEGADO":
                        self.desenhar_banner_status(frame_recortado, "NEGADO", (0, 0, 230))

                # Conversão do frame para exibição no PyQt
                frame_rgb = cv2.cvtColor(frame_recortado, cv2.COLOR_BGR2RGB)
                altura_f, largura_f, canais = frame_rgb.shape
                bytes_por_linha = canais * largura_f
                
                imagem_qt = QImage(
                    frame_rgb.data, largura_f, altura_f, bytes_por_linha, QImage.Format.Format_RGB888
                )
                
                imagem_redimensionada = imagem_qt.scaled(
                    450, 800, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                
                self.frame_signal.emit(imagem_redimensionada, frame_limpo)
                
            self.msleep(30)
            
        webcam.release()

    def parar(self):
        self.executando = False
        self.wait()


# ==============================================================================
# JANELA PRINCIPAL (INTERFACE DO USUÁRIO)
# ==============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VisionGate - Retrato")
        self.setFixedSize(450, 800)
        self.last_clean_frame = None
        
        self.diretorio_raiz = "rostos_cadastrados"
        os.makedirs(self.diretorio_raiz, exist_ok=True)
        
        # Controle de Autenticação de Administrador (PIN/Senha)
        self.admin_autenticado = False

        # Configurações de conexões e portas padrão
        self.camera_index_atual = 0
        self.porta_serial_atual = "Automático"

        # Controle de temporização dos acessos para evitar spam no Banco/Serial
        self.ultimos_acessos_registrados = {}
        self.cooldown_registro = 8 

        # Inicialização do Hardware e Dados
        self.inicializar_banco()
        self.inicializar_serial()
        self.inicializar_ui()
        self.inicializar_camera()

    def inicializar_banco(self):
        """Garante a criação do banco de dados SQLite para os logs de acesso."""
        try:
            conexao = sqlite3.connect("historico.db")
            cursor = conexao.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS historico_acesso (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    data_hora TEXT NOT NULL
                )
            """)
            conexao.commit()
            conexao.close()
        except Exception as e:
            print(f"Erro ao criar banco de dados SQLite: {e}")

    def inicializar_serial(self):
        """Localiza e se conecta à porta USB onde o Arduino está plugado."""
        self.arduino = None
        if not SERIAL_DISPONIVEL:
            print("Biblioteca 'pyserial' não encontrada. Rodando em modo de simulação.")
            return

        try:
            if self.porta_serial_atual == "Automático":
                portas = list(serial.tools.list_ports.comports())
                if portas:
                    porta_detectada = portas[0].device
                    self.arduino = serial.Serial(porta_detectada, 9600, timeout=1)
                    print(f"Conexão automática com o Arduino na porta: {porta_detectada}")
                else:
                    print("Nenhum Arduino encontrado nas portas automáticas.")
            else:
                self.arduino = serial.Serial(self.porta_serial_atual, 9600, timeout=1)
                print(f"Conectado ao Arduino na porta selecionada: {self.porta_serial_atual}")
        except Exception as e:
            print(f"Falha na conexão serial: {e}. Executando em modo simulação.")
            self.arduino = None

    def inicializar_camera(self):
        """Inicia a Thread de captura da câmera com o índice configurado."""
        self.thread_camera = CameraThread(camera_index=self.camera_index_atual)
        self.thread_camera.frame_signal.connect(self.atualizar_tela)
        self.thread_camera.reconhecido_signal.connect(self.processar_reconhecimento)
        self.thread_camera.start()

    def inicializar_ui(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a24;
            }
            QLabel {
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit {
                background-color: #262630;
                border: 1px solid #4b6584;
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #a5b1c2;
            }
            QComboBox {
                background-color: #262630;
                border: 1px solid #4b6584;
                border-radius: 8px;
                padding: 10px;
                color: #ffffff;
                font-size: 14px;
            }
            QComboBox QAbstractItemView {
                background-color: #262630;
                color: #ffffff;
                selection-background-color: #4b6584;
            }
            QPushButton {
                background-color: #4b6584;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #57606f;
            }
            QPushButton:pressed {
                background-color: #2f3542;
            }
            QListWidget {
                background-color: #262630;
                border: 1px solid #4b6584;
                border-radius: 8px;
                color: #ffffff;
                padding: 10px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 6px;
                color: #ffffff;
                border-bottom: 1px solid #31313d;
            }
            QListWidget::item:selected {
                background-color: #4b6584;
                color: #ffffff;
                font-weight: bold;
            }
            #btn_menu {
                background-color: #262630;
                border: 1px solid #4b6584;
                border-radius: 8px;
                color: #ffffff;
                font-size: 18px;
                font-weight: bold;
            }
            #btn_menu:hover {
                background-color: #4b6584;
            }
            #btn_treinar {
                background-color: #2d3d50;
                border: 1px solid #a5b1c2;
            }
            #btn_treinar:hover {
                background-color: #4b6584;
            }
            #btn_excluir {
                background-color: #8c2d2d;
                border: 1px solid #c0392b;
            }
            #btn_excluir:hover {
                background-color: #c0392b;
            }
            #lbl_webcam_home, #lbl_webcam_cadastro {
                background-color: #101015;
                border-radius: 12px;
            }
        """)

        self.container_principal = QWidget(self)
        self.setCentralWidget(self.container_principal)
        
        self.telas = QStackedWidget(self.container_principal)
        self.telas.setGeometry(0, 0, 450, 800)

        self.criar_tela_home()
        self.criar_tela_cadastro()
        self.criar_tela_gerenciamento()
        self.criar_tela_historico()
        self.criar_tela_hardware()
        
        self.telas.addWidget(self.tela_home)
        self.telas.addWidget(self.tela_cadastro)
        self.telas.addWidget(self.tela_gerenciamento)
        self.telas.addWidget(self.tela_historico)
        self.telas.addWidget(self.tela_hardware)
        
        self.criar_menu_lateral()
        self.menu_lateral.raise_()

    def criar_tela_home(self):
        self.tela_home = QWidget()
        layout = QVBoxLayout(self.tela_home)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        barra_topo = QWidget()
        barra_topo.setFixedHeight(60)
        barra_topo.setStyleSheet("background-color: rgba(26, 26, 36, 0.85);")
        
        layout_topo = QHBoxLayout(barra_topo)
        layout_topo.setContentsMargins(20, 0, 20, 0)
        
        lbl_titulo = QLabel("FECHADURA FACIAL")
        lbl_titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #ffffff; letter-spacing: 2px;")
        
        self.btn_hamburguer = QPushButton("☰")
        self.btn_hamburguer.setObjectName("btn_menu")
        self.btn_hamburguer.setFixedSize(40, 40)
        self.btn_hamburguer.clicked.connect(self.alternar_menu_lateral)
        
        layout_topo.addWidget(lbl_titulo)
        layout_topo.addStretch()
        layout_topo.addWidget(self.btn_hamburguer)

        self.lbl_webcam_home = QLabel()
        self.lbl_webcam_home.setObjectName("lbl_webcam_home")
        self.lbl_webcam_home.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(barra_topo)
        layout.addWidget(self.lbl_webcam_home, stretch=1)

    def criar_tela_cadastro(self):
        self.tela_cadastro = QWidget()
        layout = QVBoxLayout(self.tela_cadastro)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        lbl_cadastro_titulo = QLabel("CADASTRO")
        lbl_cadastro_titulo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl_cadastro_titulo.setStyleSheet("color: #ffffff; letter-spacing: 1px;")
        layout.addWidget(lbl_cadastro_titulo)

        self.lbl_webcam_cadastro = QLabel()
        self.lbl_webcam_cadastro.setObjectName("lbl_webcam_cadastro")
        self.lbl_webcam_cadastro.setFixedSize(410, 410)
        self.lbl_webcam_cadastro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_webcam_cadastro)

        # Usando a nova caixa de toque virtualizada
        self.input_nome = TouchLineEdit(self, placeholder="Digite o Nome do Usuário")
        layout.addWidget(self.input_nome)

        self.btn_capturar = QPushButton("Capturar Rosto")
        self.btn_capturar.clicked.connect(self.capturar_e_salvar_rosto)
        layout.addWidget(self.btn_capturar)

        self.btn_treinar = QPushButton("Treinar Inteligência")
        self.btn_treinar.setObjectName("btn_treinar")
        self.btn_treinar.clicked.connect(lambda: self.treinar_ia(silencioso=False))
        layout.addWidget(self.btn_treinar)

        self.btn_voltar = QPushButton("Voltar para Início")
        self.btn_voltar.setStyleSheet("""
            background-color: transparent;
            border: 1px solid #4b6584;
            color: #ffffff;
        """)
        self.btn_voltar.clicked.connect(self.voltar_para_home)
        layout.addWidget(self.btn_voltar)

    def criar_tela_gerenciamento(self):
        self.tela_gerenciamento = QWidget()
        layout = QVBoxLayout(self.tela_gerenciamento)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        lbl_gerenciar_titulo = QLabel("GERENCIAR")
        lbl_gerenciar_titulo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl_gerenciar_titulo.setStyleSheet("color: #ffffff; letter-spacing: 1px;")
        layout.addWidget(lbl_gerenciar_titulo)

        lbl_subtitulo = QLabel("Selecione um usuário cadastrado para gerenciar:")
        lbl_subtitulo.setFont(QFont("Segoe UI", 11))
        lbl_subtitulo.setStyleSheet("color: #a5b1c2;")
        layout.addWidget(lbl_subtitulo)

        self.lista_usuarios = QListWidget()
        layout.addWidget(self.lista_usuarios)

        layout_botoes = QHBoxLayout()
        layout_botoes.setSpacing(10)

        self.btn_atualizar_lista = QPushButton("Recarregar")
        self.btn_atualizar_lista.clicked.connect(self.carregar_usuarios_cadastrados)
        layout_botoes.addWidget(self.btn_atualizar_lista)

        self.btn_excluir = QPushButton("Excluir Usuário")
        self.btn_excluir.setObjectName("btn_excluir")
        self.btn_excluir.clicked.connect(self.excluir_usuario_selecionado)
        layout_botoes.addWidget(self.btn_excluir)

        layout.addLayout(layout_botoes)

        self.btn_voltar_gerenciar = QPushButton("Voltar para Início")
        self.btn_voltar_gerenciar.setStyleSheet("""
            background-color: transparent;
            border: 1px solid #4b6584;
            color: #ffffff;
        """)
        self.btn_voltar_gerenciar.clicked.connect(self.voltar_para_home)
        layout.addWidget(self.btn_voltar_gerenciar)

    def criar_tela_historico(self):
        self.tela_historico = QWidget()
        layout = QVBoxLayout(self.tela_historico)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        lbl_historico_titulo = QLabel("HISTÓRICO")
        lbl_historico_titulo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl_historico_titulo.setStyleSheet("color: #ffffff; letter-spacing: 1px;")
        layout.addWidget(lbl_historico_titulo)

        self.lista_historico = QListWidget()
        layout.addWidget(self.lista_historico)

        layout_botoes = QHBoxLayout()
        layout_botoes.setSpacing(10)

        self.btn_limpar_historico = QPushButton("Limpar Histórico")
        self.btn_limpar_historico.setObjectName("btn_excluir")
        self.btn_limpar_historico.clicked.connect(self.limpar_historico_db)
        layout_botoes.addWidget(self.btn_limpar_historico)

        self.btn_recarregar_historico = QPushButton("Atualizar")
        self.btn_recarregar_historico.clicked.connect(self.carregar_dados_historico)
        layout_botoes.addWidget(self.btn_recarregar_historico)

        layout.addLayout(layout_botoes)

        self.btn_voltar_historico = QPushButton("Voltar para Início")
        self.btn_voltar_historico.setStyleSheet("""
            background-color: transparent;
            border: 1px solid #4b6584;
            color: #ffffff;
        """)
        self.btn_voltar_historico.clicked.connect(self.voltar_para_home)
        layout.addWidget(self.btn_voltar_historico)

    def criar_tela_hardware(self):
        """Tela para selecionar as conexões físicas de Entrada de Vídeo e Porta COM do Arduino."""
        self.tela_hardware = QWidget()
        layout = QVBoxLayout(self.tela_hardware)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        lbl_hardware_titulo = QLabel("HARDWARE")
        lbl_hardware_titulo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl_hardware_titulo.setStyleSheet("color: #ffffff; letter-spacing: 1px;")
        layout.addWidget(lbl_hardware_titulo)

        lbl_hardware_desc = QLabel("Gerencie e configure os dispositivos de comunicação do totem.")
        lbl_hardware_desc.setFont(QFont("Segoe UI", 10))
        lbl_hardware_desc.setStyleSheet("color: #a5b1c2;")
        layout.addWidget(lbl_hardware_desc)

        # Seletor de Câmera (Índice USB)
        lbl_camera = QLabel("Selecionar Câmera / Porta USB:")
        lbl_camera.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(lbl_camera)

        self.combo_camera = QComboBox()
        self.combo_camera.addItems(["0 (Câmera Integrada)", "1 (Câmera USB Externa)", "2", "3"])
        layout.addWidget(self.combo_camera)

        # Seletor de Porta de Conexão Arduino (Porta COM)
        lbl_serial = QLabel("Porta COM do Arduino:")
        lbl_serial.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(lbl_serial)

        self.combo_serial = QComboBox()
        layout.addWidget(self.combo_serial)

        self.btn_atualizar_portas = QPushButton("Recarregar Portas Disponíveis")
        self.btn_atualizar_portas.setStyleSheet("background-color: #2d3d50;")
        self.btn_atualizar_portas.clicked.connect(self.recarregar_portas_dispositivos)
        layout.addWidget(self.btn_atualizar_portas)

        layout.addStretch()

        self.btn_aplicar_hardware = QPushButton("Salvar e Conectar Dispositivos")
        self.btn_aplicar_hardware.clicked.connect(self.aplicar_configuracoes_hardware)
        layout.addWidget(self.btn_aplicar_hardware)

        self.btn_voltar_hardware = QPushButton("Voltar para Início")
        self.btn_voltar_hardware.setStyleSheet("""
            background-color: transparent;
            border: 1px solid #4b6584;
            color: #ffffff;
        """)
        self.btn_voltar_hardware.clicked.connect(self.voltar_para_home)
        layout.addWidget(self.btn_voltar_hardware)

    def criar_menu_lateral(self):
        self.menu_lateral = QFrame(self.container_principal)
        self.menu_lateral.setGeometry(450, 0, 250, 800)
        self.menu_lateral.setStyleSheet("""
            QFrame {
                background-color: #262630;
                border-left: 2px solid #4b6584;
            }
            QPushButton {
                background-color: #1a1a24;
                border: 1px solid #4b6584;
                text-align: left;
                padding-left: 15px;
            }
            QPushButton:hover {
                background-color: #4b6584;
            }
        """)

        layout_menu = QVBoxLayout(self.menu_lateral)
        layout_menu.setContentsMargins(15, 40, 15, 20)
        layout_menu.setSpacing(12)

        lbl_menu_titulo = QLabel("CONFIGURAÇÕES")
        lbl_menu_titulo.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_menu_titulo.setStyleSheet("color: #a5b1c2; letter-spacing: 1px; margin-bottom: 20px;")
        layout_menu.addWidget(lbl_menu_titulo)

        btn_opt_cadastro = QPushButton("👤 Cadastrar Rosto")
        btn_opt_cadastro.clicked.connect(self.ir_para_cadastro)
        layout_menu.addWidget(btn_opt_cadastro)

        btn_opt_gerenciar = QPushButton("👥 Gerenciar Usuários")
        btn_opt_gerenciar.clicked.connect(self.ir_para_gerenciamento)
        layout_menu.addWidget(btn_opt_gerenciar)

        btn_opt_historico = QPushButton("📋 Histórico de Acessos")
        btn_opt_historico.clicked.connect(self.ir_para_historico)
        layout_menu.addWidget(btn_opt_historico)

        btn_opt_hardware = QPushButton("⚙️ Conexões e Hardware")
        btn_opt_hardware.clicked.connect(self.ir_para_hardware)
        layout_menu.addWidget(btn_opt_hardware)

        layout_menu.addStretch()

        btn_fechar = QPushButton("✕ Fechar Menu")
        btn_fechar.setStyleSheet("background-color: #4b6584; border: none; text-align: center; padding-left: 0;")
        btn_fechar.clicked.connect(self.alternar_menu_lateral)
        layout_menu.addWidget(btn_fechar)

        self.menu_aberto = False

    def alternar_menu_lateral(self):
        # 1. Se o menu estiver fechado e o usuário NÃO estiver autenticado, exige a Senha de Admin
        if not self.menu_aberto and not self.admin_autenticado:
            dialog_auth = AdminAuthDialog(self)
            if dialog_auth.exec() == QDialog.DialogCode.Accepted:
                self.admin_autenticado = True
            else:
                return # Cancela a abertura do menu se clicar fora ou errar a Senha

        # 2. Executa a animação de deslizamento do menu
        self.animacao_menu = QPropertyAnimation(self.menu_lateral, b"geometry")
        self.animacao_menu.setDuration(250)
        
        if not self.menu_aberto:
            self.animacao_menu.setStartValue(QRect(450, 0, 250, 800))
            self.animacao_menu.setEndValue(QRect(200, 0, 250, 800))
            self.menu_aberto = True
        else:
            self.animacao_menu.setStartValue(QRect(200, 0, 250, 800))
            self.animacao_menu.setEndValue(QRect(450, 0, 250, 800))
            self.menu_aberto = False
            
        self.animacao_menu.start()

    # ==============================================================================
    # GERENCIAMENTO DE CONEXÕES & HARDWARE
    # ==============================================================================
    def recarregar_portas_dispositivos(self):
        """Mapeia os canais físicos seriais conectados à placa do PC."""
        self.combo_serial.clear()
        self.combo_serial.addItem("Automático")
        
        if SERIAL_DISPONIVEL:
            portas = list(serial.tools.list_ports.comports())
            for porta in portas:
                self.combo_serial.addItem(porta.device)
        else:
            self.combo_serial.addItem("Simulação (Serial Indisponível)")

    def aplicar_configuracoes_hardware(self):
        """Desliga e reinicia os dispositivos para aplicar os novos endereços."""
        novo_index_camera = self.combo_camera.currentIndex()
        nova_porta_serial = self.combo_serial.currentText()

        # Se a câmera mudou de índice, reinicia a Thread de captura
        if novo_index_camera != self.camera_index_atual:
            self.camera_index_atual = novo_index_camera
            self.thread_camera.parar()
            self.inicializar_camera()
            print(f"[HARDWARE] Transmissão de vídeo alterada para o canal: {self.camera_index_atual}")

        # Altera a porta serial do controlador Arduino
        self.porta_serial_atual = nova_porta_serial
        if self.arduino and self.arduino.is_open:
            self.arduino.close()
        
        self.inicializar_serial()

        QMessageBox.information(
            self, "Configurações Salvas", 
            "As definições de conexões físicas foram sincronizadas e os dispositivos reiniciados com sucesso!"
        )

    # ==============================================================================
    # NAVEGAÇÃO DE TELAS
    # ==============================================================================
    def ir_para_cadastro(self):
        self.alternar_menu_lateral()
        self.thread_camera.modo = "cadastro"
        self.telas.setCurrentIndex(1)

    def ir_para_gerenciamento(self):
        self.alternar_menu_lateral()
        self.carregar_usuarios_cadastrados()
        self.thread_camera.modo = "cadastro"
        self.telas.setCurrentIndex(2)

    def ir_para_historico(self):
        self.alternar_menu_lateral()
        self.carregar_dados_historico()
        self.thread_camera.modo = "cadastro"
        self.telas.setCurrentIndex(3)

    def ir_para_hardware(self):
        self.alternar_menu_lateral()
        self.recarregar_portas_dispositivos()
        self.thread_camera.modo = "cadastro"
        self.telas.setCurrentIndex(4)

    def voltar_para_home(self):
        # SEGURANÇA: Bloqueia novamente o painel de administração ao retornar para a tela inicial
        self.admin_autenticado = False
        self.thread_camera.modo = "reconhecimento"
        self.telas.setCurrentIndex(0)

    # ==============================================================================
    # COMUNICAÇÃO SERIAL E BANCO DE DADOS
    # ==============================================================================
    def processar_reconhecimento(self, nome_usuario):
        """Disparado no momento exato em que um rosto cadastrado é reconhecido."""
        agora = datetime.now()
        ultimo_registro = self.ultimos_acessos_registrados.get(nome_usuario)

        # Evita loops redundantes de liberação enquanto o usuário estiver parado na tela
        if ultimo_registro and (agora - ultimo_registro).total_seconds() < self.cooldown_registro:
            return

        self.ultimos_acessos_registrados[nome_usuario] = agora
        nome_amigavel = nome_usuario.replace("_", " ").title()

        # 1. Aciona o Arduino via Porta Serial
        if self.arduino and self.arduino.is_open:
            try:
                # Envia o caractere '1' para disparar o Relé da fechadura
                self.arduino.write(b'1')
                print(f"[SERIAL] Comando de liberação ('1') enviado para o Arduino! Usuário: {nome_amigavel}")
            except Exception as e:
                print(f"[SERIAL] Erro ao comunicar com o Arduino: {e}")
        else:
            print(f"[SIMULADO] Porta Liberada! (Sem Arduino conectado). Usuário: {nome_amigavel}")

        # 2. Grava o log no banco de dados SQLite
        try:
            conexao = sqlite3.connect("historico.db")
            cursor = conexao.cursor()
            data_hora_atual = agora.strftime("%d/%m/%Y %H:%M:%S")
            
            cursor.execute(
                "INSERT INTO historico_acesso (nome, data_hora) VALUES (?, ?)", 
                (nome_amigavel, data_hora_atual)
            )
            conexao.commit()
            conexao.close()
            print(f"[BANCO DE DADOS] Acesso de '{nome_amigavel}' gravado em {data_hora_atual}")
        except Exception as e:
            print(f"[BANCO DE DADOS] Falha ao registrar log no SQLite: {e}")

    def atualizar_tela(self, imagem_qt, frame_limpo):
        if self.telas.currentIndex() == 0:
            self.lbl_webcam_home.setPixmap(QPixmap.fromImage(imagem_qt))
        elif self.telas.currentIndex() == 1:
            preview_menor = imagem_qt.scaled(
                410, 410, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_webcam_cadastro.setPixmap(QPixmap.fromImage(preview_menor))
            
        self.last_clean_frame = frame_limpo

    # ==============================================================================
    # FUNÇÕES DE LEITURA E LIMPEZA DO HISTÓRICO (SQLITE)
    # ==============================================================================
    def carregar_dados_historico(self):
        """Lê os logs armazenados na tabela do banco e preenche a lista na interface."""
        self.lista_historico.clear()
        try:
            conexao = sqlite3.connect("historico.db")
            cursor = conexao.cursor()
            cursor.execute("SELECT nome, data_hora FROM historico_acesso ORDER BY id DESC")
            registros = cursor.fetchall()
            conexao.close()

            for nome, data_hora in registros:
                texto_item = f"🔓 Porta Liberada para: {nome}\n📅 {data_hora}"
                item = QListWidgetItem(texto_item)
                self.lista_historico.addItem(item)
        except Exception as e:
            print(f"Erro ao carregar dados do SQLite: {e}")

    def limpar_historico_db(self):
        """Apaga permanentemente os registros da tabela de acessos do SQLite."""
        confirmacao = QMessageBox.question(
            self, "Limpar Histórico",
            "Tem certeza de que deseja deletar todos os logs de acesso permanentemente?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirmacao == QMessageBox.StandardButton.Yes:
            try:
                conexao = sqlite3.connect("historico.db")
                cursor = conexao.cursor()
                cursor.execute("DELETE FROM historico_acesso")
                conexao.commit()
                conexao.close()
                self.carregar_dados_historico()
                QMessageBox.information(self, "Sucesso", "O histórico de acessos foi completamente limpo!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Não foi possível limpar os registros: {e}")

    # ==============================================================================
    # EXCLUSÃO E GERENCIAMENTO DE CADASTROS
    # ==============================================================================
    def carregar_usuarios_cadastrados(self):
        self.lista_usuarios.clear()
        if os.path.exists(self.diretorio_raiz):
            subpastas = [d for d in os.listdir(self.diretorio_raiz) if os.path.isdir(os.path.join(self.diretorio_raiz, d))]
            for pasta in sorted(subpastas):
                nome_formatado = pasta.replace("_", " ").title()
                item = QListWidgetItem(nome_formatado)
                item.setData(Qt.ItemDataRole.UserRole, pasta)
                self.lista_usuarios.addItem(item)

    def excluir_usuario_selecionado(self):
        item_selecionado = self.lista_usuarios.currentItem()
        if not item_selecionado:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione um usuário da lista para excluir!")
            return

        pasta_usuario = item_selecionado.data(Qt.ItemDataRole.UserRole)
        nome_exibicao = item_selecionado.text()

        confirmacao = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Tem certeza que deseja excluir o cadastro de '{nome_exibicao}' permanentemente?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirmacao == QMessageBox.StandardButton.Yes:
            caminho_completo = os.path.join(self.diretorio_raiz, pasta_usuario)
            try:
                shutil.rmtree(caminho_completo)
                self.carregar_usuarios_cadastrados()
                self.treinar_ia(silencioso=True)
                QMessageBox.information(self, "Sucesso", f"O cadastro de '{nome_exibicao}' foi deletado.")
            except Exception as e:
                QMessageBox.critical(self, "Erro de Exclusão", f"Não foi possível remover a pasta: {e}")

    # ==============================================================================
    # SALVAR ROSTO E TREINAR IA
    # ==============================================================================
    def capturar_e_salvar_rosto(self):
        nome_usuario = self.input_nome.text().strip()

        if not nome_usuario:
            QMessageBox.warning(self, "Aviso", "Por favor, digite o nome para realizar o registro!")
            return

        if self.last_clean_frame is None:
            QMessageBox.warning(self, "Erro", "Webcam não carregada!")
            return

        nome_limpo = re.sub(r'[\\/*?:"<>|]', "", nome_usuario).replace(" ", "_").lower()

        frame_cinza = cv2.cvtColor(self.last_clean_frame, cv2.COLOR_BGR2GRAY)
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        rostos = detector.detectMultiScale(frame_cinza, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

        if len(rostos) == 0:
            QMessageBox.critical(self, "Erro de Captura", "Nenhum rosto detectado! Reposicione-se.")
            return

        pasta_usuario = os.path.join(self.diretorio_raiz, nome_limpo)
        os.makedirs(pasta_usuario, exist_ok=True)

        (x, y, largura, altura) = rostos[0]
        margem = int(largura * 0.1)
        y_inicial = max(0, y - margem)
        y_final = min(self.last_clean_frame.shape[0], y + altura + margem)
        x_inicial = max(0, x - margem)
        x_final = min(self.last_clean_frame.shape[1], x + largura + margem)

        rosto_recortado = self.last_clean_frame[y_inicial:y_final, x_inicial:x_final]
        rosto_cinza = cv2.cvtColor(rosto_recortado, cv2.COLOR_BGR2GRAY)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"{nome_limpo}_{timestamp}.jpg"
        caminho_completo = os.path.join(pasta_usuario, nome_arquivo)

        sucesso = cv2.imwrite(caminho_completo, rosto_cinza)

        if sucesso:
            total_fotos = len([f for f in os.listdir(pasta_usuario) if f.endswith('.jpg')])
            QMessageBox.information(
                self, "Cadastro Concluído", 
                f"Rosto cadastrado com sucesso! Total na pasta de {nome_usuario.title()}: {total_fotos} fotos."
            )
            self.input_nome.clear()
        else:
            QMessageBox.critical(self, "Erro de E/S", "Não foi possível salvar o arquivo de imagem.")

    def treinar_ia(self, silencioso=False):
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        faces_treino = []
        ids_treino = []
        labels_map = {}
        
        subpastas = [d for d in os.listdir(self.diretorio_raiz) if os.path.isdir(os.path.join(self.diretorio_raiz, d))]
        
        if not subpastas:
            if os.path.exists("classificador_lbph.yml"):
                os.remove("classificador_lbph.yml")
            if os.path.exists("labels.json"):
                os.remove("labels.json")
            self.thread_camera.carregar_modelo()
            if not silencioso:
                QMessageBox.warning(self, "Erro", "A pasta de cadastros está vazia!")
            return

        for index_id, nome_pasta in enumerate(subpastas):
            labels_map[index_id] = nome_pasta
            caminho_pasta = os.path.join(self.diretorio_raiz, nome_pasta)
            
            for arquivo in os.listdir(caminho_pasta):
                if arquivo.lower().endswith(('.jpg', '.jpeg', '.png')):
                    caminho_imagem = os.path.join(caminho_pasta, arquivo)
                    imagem_np = cv2.imread(caminho_imagem, cv2.IMREAD_GRAYSCALE)
                    
                    rostos = detector.detectMultiScale(imagem_np, scaleFactor=1.1, minNeighbors=5)
                    for (x, y, largura, altura) in rostos:
                        faces_treino.append(imagem_np[y:y+altura, x:x+largura])
                        ids_treino.append(index_id)

        if len(faces_treino) == 0:
            if os.path.exists("classificador_lbph.yml"):
                os.remove("classificador_lbph.yml")
            if os.path.exists("labels.json"):
                os.remove("labels.json")
            self.thread_camera.carregar_modelo()
            if not silencioso:
                QMessageBox.warning(self, "Erro", "Nenhum rosto válido foi encontrado para o treinamento.")
            return

        try:
            reconhecedor = cv2.face.LBPHFaceRecognizer_create()
            reconhecedor.train(faces_treino, np.array(ids_treino))
            reconhecedor.write("classificador_lbph.yml")
            
            with open("labels.json", "w", encoding="utf-8") as f:
                json.dump(labels_map, f, indent=4, ensure_ascii=False)
                
            self.thread_camera.carregar_modelo()
            if not silencioso:
                QMessageBox.information(self, "Sucesso!", "A Inteligência Artificial foi treinada!")
        except Exception as e:
            if not silencioso:
                QMessageBox.critical(self, "Erro", f"Houve um problema durante o treinamento: {e}")

    # ==============================================================================
    # FECHAMENTO DO PROGRAMA
    # ==============================================================================
    def closeEvent(self, event):
        self.thread_camera.parar()
        if self.arduino and self.arduino.is_open:
            self.arduino.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    janela = MainWindow()
    janela.show()
    sys.exit(app.exec())