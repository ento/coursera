.. _{{ title }}:

{{ title }}
{{ '=' * title|length }}

.. toctree::
   :maxdepth: 1

{% for entry_type, entry in entries %}
   {{ entry }}{% if not entry_type %}/index{% endif %}
{%-endfor %}
