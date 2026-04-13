import logging

import anthropic

logger = logging.getLogger(__name__)


class Researcher:
    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def research_contact(self, contact: dict) -> dict:
        name = contact.get("name", "")
        company = contact.get("company", "")
        email = contact.get("email", "")

        prompt = (
            f"Research this person and return a brief summary:\n"
            f"Name: {name}\n"
            f"Company: {company}\n"
            f"Email: {email}\n\n"
            f"Find:\n"
            f"1. Their current role and company (may have changed)\n"
            f"2. Any recent news about them or their company (last 6 months)\n"
            f"3. One specific, concrete detail that could personalize an outreach email "
            f"(a product launch, funding round, award, article, or notable activity)\n\n"
            f"Be concise. Respond in this exact JSON format:\n"
            f'{{\n'
            f'  "current_role": "...",\n'
            f'  "current_company": "...",\n'
            f'  "recent_news": "1-2 sentences of relevant recent news",\n'
            f'  "personalization_hook": "one specific detail to reference in an email",\n'
            f'  "linkedin_url": "url or null",\n'
            f'  "confidence": "high|medium|low"\n'
            f'}}\n\n'
            f"Return ONLY valid JSON, no other text."
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            # Agentic loop: let Claude call web search as needed
            while True:
                response = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=messages,
                )

                if response.stop_reason == "end_turn":
                    # Extract the final text response
                    text = next(
                        (b.text for b in response.content if hasattr(b, "text")), ""
                    ).strip()
                    break

                if response.stop_reason == "tool_use":
                    # Add assistant turn and tool results, then continue
                    messages.append({"role": "assistant", "content": response.content})
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": block.input.get("query", ""),
                                }
                            )
                    messages.append({"role": "user", "content": tool_results})
                else:
                    # Unexpected stop reason
                    text = ""
                    break

            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            result = {
                "current_role": "",
                "current_company": company,
                "recent_news": "",
                "personalization_hook": "",
                "linkedin_url": None,
                "confidence": "low",
            }
            if text:
                import json
                parsed = json.loads(text)
                result.update(parsed)

            logger.info(
                f"Research complete for {name}: confidence={result['confidence']}"
            )
            return result

        except Exception as e:
            logger.warning(f"Research failed for {name}: {e}")
            return {
                "current_role": "",
                "current_company": company,
                "recent_news": "",
                "personalization_hook": "",
                "linkedin_url": None,
                "confidence": "low",
            }

    def research_all_contacts(self, contacts: list[dict]) -> list[dict]:
        enriched = []
        for contact in contacts:
            logger.info(
                f"Researching {contact.get('name')} at {contact.get('company')}..."
            )
            research = self.research_contact(contact)
            enriched.append({**contact, "research": research})
        return enriched
