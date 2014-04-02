.. _{{ title }}:

:doc:`/index`{% if crumbs %}{% for crumb in crumbs[:-1] %} / :ref:`{{ crumb }}`{% endfor %}{% endif %}

{{ title }}
{{ '=' * title|length }}

.. toctree::
   :maxdepth: 1

{% for entry_type, entry in entries %}
   {{ entry }}{% if not entry_type %}/index{% endif %}
{%-endfor %}
