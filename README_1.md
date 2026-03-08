# Pitch: The Autonomous Chess Economy

## 1. The Vision: From Game Players to Autonomous Businesses

The hackathon challenges us to build "autonomous businesses where agents make real economic decisions." We propose to meet this challenge by creating a dynamic, multi-agent economic simulation where the "business" is competitive chess. Our project, **The Autonomous Chess Economy**, transforms a multi-agent chess RL system into a living marketplace where AI agents, acting as solo founders, make strategic financial decisions to maximize their profit.

> In our system, agents don’t just play chess; they run a business. They pay to enter tournaments, purchase services from other agents, and compete for real prize money, all in a fully autonomous loop. This directly addresses the hackathon's core theme of agents with "real execution authority: transacting with each other, earning and spending money, and operating under real constraints."

## 2. The Architecture: A Multi-Layered Economic Simulation

We extend our existing multi-agent chess platform by introducing a new economic layer. This layer governs all financial transactions and decisions, turning a simple game environment into a complex economic simulation.

![Autonomous Economic Agent Architecture](https://private-us-east-1.manuscdn.com/sessionFile/ELP96X8OiHqgxiSAuWbFms/sandbox/DkQnI6BiqjsJuDKZwKYaEL-images_1772590773264_na1fn_L2hvbWUvdWJ1bnR1L2Vjb25vbWljX2FnZW50X2FyY2hpdGVjdHVyZQ.png?Policy=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9wcml2YXRlLXVzLWVhc3QtMS5tYW51c2Nkbi5jb20vc2Vzc2lvbkZpbGUvRUxQOTZYOE9pSHFneGlTQXVXYkZtcy9zYW5kYm94L0RrUW5JNkJpcWpzSnVES1p3S1lhRUwtaW1hZ2VzXzE3NzI1OTA3NzMyNjRfbmExZm5fTDJodmJXVXZkV0oxYm5SMUwyVmpiMjV2YldsalgyRm5aVzUwWDJGeVkyaHBkR1ZqZEhWeVpRLnBuZyIsIkNvbmRpdGlvbiI6eyJEYXRlTGVzc1RoYW4iOnsiQVdTOkVwb2NoVGltZSI6MTc5ODc2MTYwMH19fV19&Key-Pair-Id=K2HSFNDJXOU9YS&Signature=rNPEVwChkPDeMlLFncPZ3h9LMOF8RO71jI~pnNlc6NcjqopfaO1QhBL0NuEmo9Ef26L5G3l6pbGddJoOcRGoj8G2G-4NPW7aJBAOg96JDHSLaQqba4dIo9buQZENchWYVYC06wPCmIZ0rEy-JrA7356pR-yaM8THbJ~EAMLN-S31Uaon3FSJ9YcIlAdF113Vp46Znid6UE0rWF9QbKYk8egTGEy5KPRbxajLXch4KCJPy5G9ZCxYyv8D4Vz8FWIPtCfxUX1R9sX6TB64Qz~d3DNP0fbpwNCoGn1tAzPXMPJ0u7XWr87DdSKKlatL8ed5Qz86bDTk2Em75s-l8f6zww__)

Our architecture is composed of three primary layers:

1.  **The Market Layer:** A **Tournament Organizer** agent acts as the central marketplace. It collects entry fees from participants and manages a prize pool, creating the fundamental economic incentive for the system.
2.  **The Agent Layer:** This layer consists of two types of autonomous businesses:
    *   **Player Agents (The Competitors):** These are the core businesses in our economy. Each Player Agent is an RL-trained model that aims to maximize its profit by winning tournaments. They start with a seed budget and must make strategic decisions about how to allocate their capital.
    *   **Service Agents (The Consultants):** These agents represent specialized service providers. For example, a **Coach Agent** (powered by a strong engine like Stockfish or an LLM analyst) can sell move analysis or strategic advice for a fee. This creates a B2B market within our ecosystem.
3.  **The Transaction & Decision Layer:** This is where the economic decisions are made and executed. When a Player Agent faces a difficult position, it must decide: *is it worth paying a fee to a Coach Agent for advice?* This decision is a core part of the agent's policy. If the agent decides to buy, a transaction is executed via a lightweight, agent-native payment protocol like **x402**, enabling instant, autonomous agent-to-agent payments [1][2].

## 3. The Economic Model: Profit, Loss, and ROI

The economic model is designed to mirror real-world business constraints:

| Economic Component | Business Analogy | Implementation |
| :--- | :--- | :--- |
| **Tournament Entry Fee** | **Cost of Goods Sold (COGS)** | A fixed fee paid by each Player Agent to the Tournament Organizer to enter a game. |
| **Prize Pool** | **Revenue** | The winner of the game receives the prize pool (e.g., 1.8x the total entry fees). |
| **Service Payments** | **Operating Expenses (OpEx)** | Player Agents can choose to pay Coach Agents for services, creating a cost-benefit trade-off. |
| **Agent Wallet** | **Company Treasury** | Each agent maintains a wallet (e.g., with a starting balance of 100 units) to manage its funds. |
| **Profit/Loss** | **Net Income** | The agent's success is measured not just by its win rate, but by its net profit over time. |

This model forces the agents to learn a sophisticated policy that balances short-term costs (paying for coaching) with long-term gains (winning the tournament). An agent that spends too much on coaching may win games but still go bankrupt. A successful agent learns to be a shrewd business operator, identifying the critical moments where paying for a service provides a positive return on investment (ROI).

## 4. The RL Problem: Maximizing Profit, Not Just Wins

This economic layer transforms the reinforcement learning problem from simply maximizing wins to **maximizing profit**. The RL agent's objective is now explicitly financial.

*   **State:** The agent's observation space is expanded to include not only the chess board state but also its current **wallet balance** and the **prices of available services**.
*   **Action:** The action space is expanded beyond just chess moves. The agent can now take **economic actions**, such as `buy_analysis_from_coach_X`.
*   **Reward:** The reward function is no longer a simple `+1` for a win. Instead, the reward is the **change in the agent's wallet balance**. A win provides a large positive reward (the prize money), while paying for a service results in a small negative reward (the cost). The RL algorithm (e.g., GRPO, PPO) will optimize the agent's policy to maximize this cumulative financial reward.

## 5. Why This Project Fits the Hackathon

This project is a direct and compelling implementation of the hackathon's vision:

*   **Autonomous Economic Decisions:** Agents decide what to buy (coaching services), who to pay (which coach), when to switch (if a coach is not providing value), and when to stop (if a game is unwinnable and further expense is futile).
*   **Real Execution Authority:** Agents autonomously transact with each other using a real payment protocol, earning and spending money without human intervention.
*   **Scalable Businesses for Solo Founders:** Our architecture demonstrates how a single person can launch a complex, self-sustaining digital economy. The Tournament Organizer and Coach Agents are autonomous entities that can operate and grow with minimal oversight, creating a scalable business model powered by AI agents.

By building The Autonomous Chess Economy, we are not just creating a better chess-playing AI; we are creating a microcosm of a future where autonomous agents can participate in and shape economic activity.

## 6. References

[1] [x402 - Payment Required | Internet-Native Payments Standard](https://www.x402.org/)
[2] [Agentic Payments: x402 and AI Agents in the AI Economy - Galaxy Digital](https://www.galaxy.com/insights/research/x402-ai-agents-crypto-payments)
[3] [AI Agents & The New Payment Infrastructure - The Business Engineer](https://businessengineer.ai/p/ai-agents-and-the-new-payment-infrastructure)
[4] [Introducing Agentic Wallets - Coinbase](https://www.coinbase.com/developer-platform/discover/launches/agentic-wallets)

