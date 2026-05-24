# FECHADURA-RECONHECIMENTO-FACIAL
Fechadura eletrônica com python e arduino

# 👁️ Reconhecimento Facial em Tempo Real com Python

Este é um projeto de reconhecimento facial que utiliza a webcam do computador para identificar pessoas em tempo real. O sistema utiliza técnicas de Inteligência Artificial para mapear traços faciais, gerar uma assinatura digital única para cada rosto e compará-la com fotos previamente conhecidas.

---

## 🚀 Como Funciona por Trás dos Panos?

O sistema opera em 4 etapas principais a cada frame capturado da webcam:
1. **Detecção:** Localiza onde existem rostos na imagem.
2. **Mapeamento:** Encontra 68 pontos de referência (olhos, nariz, boca e contorno).
3. **Codificação (Embeddings):** Transforma esses traços em um vetor matemático de 128 números.
4. **Comparação:** Calcula a distância de similaridade entre o rosto da webcam e a foto salva. Se a distância for pequena, a identidade é confirmada!

> 💡 **Truque de Performance:** Para garantir que o vídeo rode liso e sem travamentos (lag), o frame da webcam é reduzido para 25% do seu tamanho original durante o processamento de IA, e depois redimensionado de volta para desenhar os retângulos na tela.


    Lista de Bibliotecas
opencv-python: Captura o vídeo da webcam e manipula as imagens.
face-recognition: Detecta os rostos e extrai as assinaturas faciais.
numpy: Realiza o cálculo matemático rápido para comparar os rostos.
pyserial (ou pyFirmata): Biblioteca necessária para fazer o Python conversar com o Arduino/Microcontrolador via porta USB.

Resumo do Funcionamento (Da Webcam ao Solenóide)
[ Webcam ] ➡️ [ Python (IA) ] ➡️ [ Serial/USB ] ➡️ [ Arduino ] ➡️ [ Relé ] ➡️ [ Solenóide ]