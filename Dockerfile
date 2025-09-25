# Multi-stage build para otimizar tamanho da imagem
FROM python:3.11-slim as builder

# Instalar dependências do sistema necessárias para compilação
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage final - imagem de produção
FROM python:3.11-slim

# Instalar dependências de runtime
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Criar diretórios necessários
RUN mkdir -p /app /tmp/reports && \
    chown -R appuser:appuser /app /tmp/reports

# Copiar dependências Python do stage anterior
COPY --from=builder /root/.local /home/appuser/.local

# Definir PATH para incluir dependências locais
ENV PATH=/home/appuser/.local/bin:$PATH

# Definir diretório de trabalho
WORKDIR /app

# Copiar código da aplicação
COPY app/ ./app/

# Alterar propriedade dos arquivos
RUN chown -R appuser:appuser /app

# Mudar para usuário não-root
USER appuser

# Expor porta
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Comando para executar a aplicação
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
