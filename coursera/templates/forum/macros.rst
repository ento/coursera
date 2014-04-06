{% macro render_post(post, is_comment=False) %}
{%-set style_class = 'post' if not is_comment else 'comment' %}
.. raw:: html

   <div class="text-container text-container-{{ style_class }}" id="{{ style_class }}-{{ post.id }}">
    <div class="text-container-header">
      {% if post.anonymous %}Anonymous{% else %}{{ post._user_full_name }}{% endif %}
      {%-if post._user_title and post._user_title != 'Student' %}<span class="profile-badge">{{ post._user_title }}</span>{%-endif %}
      &middot; {{ post.post_time|timestamp }}
     </div>
{{ post|html(is_comment)|safe|indent(3, true) }}
     <div class="text-container-footer">
     {%-if post.votes %}
       <span>{% if post.votes > 0 %}&uarr;{% else %}&darr;{% endif %}{{ post.votes|abs }}</span>
     {%-endif %}
     </div>
   </div>

{% endmacro %}
