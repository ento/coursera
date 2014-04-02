{%-from 'forum/macros.rst' import render_post-%}
.. _{{ title }}:
.. _thread_{{ id }}:

:doc:`/index` {% for crumb in crumbs[1:] %} / :ref:`{{ crumb.title }}`{% endfor %}

{{ title }}
{{ '=' * title|length }}

{%-for post in posts if 'post_text' in post and not post.deleted %}
  {{-render_post(post)-}}
  {%-if post.id in comments_by_post %}
    {%-for comment in comments_by_post[post.id] if 'comment_text' in comment and not comment.deleted %}
      {{-render_post(comment, comment=True)-}}
    {%-endfor %}
  {%-endif %}
{%-endfor %}
