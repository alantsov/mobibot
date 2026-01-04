FROM alpine:3.22.2

RUN apk add poppler-utils
RUN apk add bash

WORKDIR /data

COPY pdf_to_png_par.sh /pdf_to_png_par.sh

RUN chmod +x /pdf_to_png_par.sh
RUN chown 777 /pdf_to_png_par.sh

ENTRYPOINT ["/pdf_to_png_par.sh", "-png", "-r", "300"]