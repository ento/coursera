:doc:`/index`{% if crumbs %}{% for crumb in crumbs[:-1] %} / :ref:`{{ crumb.ref }}`{% endfor %}{% endif %}

.. _{{ ref }}:

{{ title|escape_punctuation }}
{{ '=' * (title|length * 2) }}

.. toctree::
   :maxdepth: 1
{% for entry, ref in entries %}
   {{ entry.filename }}{% if entry.is_forum %}/index{% endif %}
{%-endfor %}
