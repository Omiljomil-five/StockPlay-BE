FROM public.ecr.aws/lambda/python:3.12

# WeasyPrint system dependencies (pango, cairo, gdk-pixbuf)
RUN dnf install -y pango cairo gdk-pixbuf2 gobject-introspection libffi-devel && dnf clean all

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lambda_handler.py email_sender.py ./
COPY src/ src/
COPY fonts/ fonts/
COPY templates/ templates/
COPY data/ data/

ENV FONTCONFIG_FILE=/var/task/fonts/fonts.conf

CMD ["lambda_handler.handler"]
