Consider context below. Each piece of information will be labelled with a header.

{% for key, value in context.items() %}
    ### {{ key }}

    {{ value }}

{% endfor %}
Using this context combined with general knowledge to answer question below. Provide the source for your answer and clearly indicate if the source is from the context or not.

Question: {{question}}

Answer: