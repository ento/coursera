{%-from 'forum/macros.rst' import render_post-%}
:doc:`/index` {% for crumb in crumbs[1:] %} / :ref:`{{ crumb|forum_ref }}`{% endfor %}

.. _{{ ref }}:

{{ title|escape_punctuation }}
{{ '=' * (title|length * 2) }}

{% for tag in tags %}:tag:`{{ tag.tag_name }}` {% endfor %}
{% for post in posts if 'post_text' in post and not post.deleted %}
  {{-render_post(post)-}}
  {%-if post.id in comments_by_post %}
    {%-for comment in comments_by_post[post.id] if 'comment_text' in comment and not comment.deleted %}
      {{-render_post(comment, is_comment=True)-}}
    {%-endfor %}
  {%-endif %}
{%-endfor %}
