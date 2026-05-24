/*
  ==============================================================================
  PROJETO VISIONGATE - CONTROLE DE ACESSO VIA RELÉ / SOLENÓIDE DE FECHADURA
  ==============================================================================
  Este sketch aguarda o caractere '1' ser enviado pela porta serial do computador.
  Ao receber este sinal, aciona um pino de saída (conectado à placa de Relé)
  para liberar a fechadura solenóide por 3 segundos antes de travá-la de novo.
*/

// Definição dos Pinos de Saída
const int PINO_RELE = 7; // Conecte o pino IN (Sinal) do módulo Relé no Pino Digital 7
const int PINO_LED_STATUS = 13; // Led nativo do Arduino para checar o funcionamento

void setup() {
  // Inicialização dos pinos como saída
  pinMode(PINO_RELE, OUTPUT);
  pinMode(PINO_LED_STATUS, OUTPUT);

  // IMPORTANTE: Módulos de relés comuns operam em LÓGICA INVERTIDA.
  // HIGH costuma manter o relé desligado, e LOW aciona o relé.
  // Caso sua placa seja diferente, inverta os estados no código!
  digitalWrite(PINO_RELE, HIGH); 
  digitalWrite(PINO_LED_STATUS, LOW);

  // Inicializa a comunicação serial a 9600 bps (igual ao Python)
  Serial.begin(9600);
}

void loop() {
  // Verifica se existem dados disponíveis vindos do computador na porta Serial
  if (Serial.available() > 0) {
    char caractere_recebido = Serial.read();

    // Se o sinal recebido for o caractere '1' (Comando enviado pelo main.py)
    if (caractere_recebido == '1') {
      
      // 1. Aciona o Relé e o LED indicador (Abre a fechadura)
      digitalWrite(PINO_RELE, LOW);         // Ativa o relé (conecta contatos COMUM e NORM. ABERTO)
      digitalWrite(PINO_LED_STATUS, HIGH);  // Liga o Led azul/verde de controle físico
      
      // 2. Mantém a porta destravada por 3 segundos (tempo para o usuário puxar a porta)
      delay(3000); 
      
      // 3. Desliga o Relé e o LED indicador (Bloqueia a fechadura novamente)
      digitalWrite(PINO_RELE, HIGH);        // Desliga o relé (corta a corrente da Solenóide)
      digitalWrite(PINO_LED_STATUS, LOW);   // Desliga o Led indicador
    }
  }
}