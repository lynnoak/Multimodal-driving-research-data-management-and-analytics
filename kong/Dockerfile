FROM kong:3.9
USER root
COPY kong.template.yml /etc/kong/kong.template.yml
COPY entrypoint.sh /custom-entrypoint.sh
RUN chmod 755 /custom-entrypoint.sh
USER kong
ENTRYPOINT ["/custom-entrypoint.sh"]
CMD ["kong", "docker-start"]
