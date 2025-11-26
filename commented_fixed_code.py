import jinja2

from django.db import models
from django.db.models import UniqueConstraint


# Default value function for new Chat instances
# Returns a dict with an empty messages array
def default_chat_stream():
    return {"messages": []}


class Prompt(models.Model):
    """
    A reusable template for starting chat conversations.
    Can include Jinja2 template variables that get filled in when creating a chat.
    """
    
    # Unique name to identify this prompt template (e.g., "customer_service_bot")
    name = models.CharField(max_length=256)
    
    # The system message that defines the AI's behavior and context
    # Can contain Jinja2 template syntax like "You are {{ role }}"
    system_prompt = models.TextField()
    
    # The first assistant message to start the conversation
    # Also supports Jinja2 templating for dynamic content
    first_message = models.TextField()

    class Meta: 
        # Ensure no two prompts can have the same name in the database
        constraints = [
            UniqueConstraint(fields=["name"], name="unique_prompt_name"),
        ]

    def materialize_chat(self, variables=None):
        """
        Creates a new Chat instance from this prompt template.
        
        Args:
            variables: Dict of values to substitute into the Jinja2 templates
                      (e.g., {"role": "helpful assistant", "name": "Alice"})
        
        Returns:
            A saved Chat object with rendered system and first assistant messages
        """
        # Default to empty dict if no variables provided
        if variables is None:
            variables = {}

        # Build the initial message structure in OpenAI format
        messages = [
            # System message sets the AI's instructions and context
            {"role": "system", "content": self._render(self.system_prompt, variables)},
            # First assistant message starts the conversation
            {
                "role": "assistant",
                "content": self._render(self.first_message, variables),
            },
        ]
        
        # Create a new Chat with these messages
        chat = Chat(messages=messages)
        
        # Save to database and return
        chat.save()
        return chat

    def _render(self, message, variables):
        """
        Renders a Jinja2 template with available snippets and variables using two-pass rendering.
        This supports variables inside snippets by rendering snippets first, then variables.
        
        Args:
            message: String containing Jinja2 template syntax
            variables: Dict of user-provided template values
        
        Returns:
            Fully rendered string with all variables substituted
        """
        # What was the issue in the initial code?

            # Jinja2 only does one-pass rendering. Once it substitutes a variable's value, it doesn't re-parse that value looking for more template syntax. 
            # This is actually a security feature in most templating engines to prevent template injection attacks.

        # Solution Approach
        
            # We need to do two-pass rendering:
                # First pass: Render snippets into the template
                # Second pass: Render variables into the result
    
            # This ensures that varriables inside snippets work (our goal) & variables in the main prompt work (existing behavior)

        # Implementation 
        
        # Two-pass rendering to support variables inside snippets
        
        # First pass: Render snippets into the template
            # Fetch all Snippet objects and convert to a dict {name: content}
            # This allows templates to reference snippets like {{ greeting_text }}
            # and expands {{ snippet_name }} with snippet content
        snippets = dict([(s.name, s.content) for s in Snippet.objects.all()])
        intermediate_template = jinja2.Template(message).render(snippets)
        
        # Second pass: Render variables into the expanded template
            # This processes any {{ variable_name }} that came from snippets or the original template
        context = snippets | variables
        final_output = jinja2.Template(intermediate_template).render(context)

        # Further Considerations:
            # Current implantation does not support nesting (one variable referring to another variable). 
            # It currently segments the render function into 2 passes (one that renders the snippet and one that subsequently renders the variable).
            # If you wanted to address the nesting scenario, you could add more passes in accordance to how deeply you want it to nest.  
            # At some point this should be limited so it does not keep nesting into infinity. 
        
        return final_output

    def __str__(self):
        # String representation for admin interface and debugging
        return self.name


class Chat(models.Model):
    """
    Represents an active chat conversation in OpenAI's message format.
    
    Messages are stored as a JSON structure:
    {
       "messages": [
          {"role": "system", "content": "You are a helpful assistant."},
          {"role": "user", "content": "Hello!"},
          {"role": "assistant", "content": "Hi there!"}
       ]
    }
    
    The wrapping object exists because Django's JSONField can be finicky
    when storing arrays at the top level.
    """
    
    # JSONField to store the entire conversation history
    # default_chat_stream provides the initial empty structure
    stream = models.JSONField(default=default_chat_stream)

    @property
    def messages(self):
        """
        Property getter for easy access to the messages array.
        Allows using chat.messages instead of chat.stream["messages"]
        """
        return self.stream["messages"]

    @messages.setter
    def messages(self, messages):
        """
        Property setter to update messages.
        
        Usage:
            chat.messages = [{"role": "user", "content": "Hi"}]
            # This updates chat.stream["messages"] behind the scenes
        """
        self.stream["messages"] = messages


class Snippet(models.Model):
    """
    Reusable text fragments that can be referenced in Prompt templates.
    
    Example:
        Snippet(name="greeting", content="Hello! Welcome to our service.")
        
        Then in a Prompt template: "{{ greeting }} How can I help?"
    """
    
    # Unique identifier to reference this snippet in templates
    name = models.CharField(max_length=256)
    
    # The actual text content to be inserted
    content = models.TextField()

    class Meta: 
        # Ensure no duplicate snippet names in the database
        constraints = [
            UniqueConstraint(fields=["name"], name="unique_snippet_name"),
        ]

    def __str__(self):
        # String representation for admin interface and debugging
        return self.name
