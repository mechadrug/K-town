package agent

import (
	"fmt"
	"time"
)

// Perceive feeds events into the agent short-term memory
func (a *Agent) Perceive(events []string) {
	for _, e := range events {
		a.Memory.AddObservation(e, 5.0)
	}
}

// Think updates beliefs and evaluates goals based on recent memory
func (a *Agent) Think(hour int) {
	// Consolidate important short-term memories into long-term
	a.Memory.Consolidate(7.0)

	// Mood shifts based on energy
	if a.State.Energy < 20 {
		a.State.Mood = MoodSad
	} else if a.State.Energy < 50 {
		a.State.Mood = MoodAnxious
	} else if a.State.Energy > 80 {
		a.State.Mood = MoodHappy
	}

	// Energy decays slightly each tick
	a.State.Energy -= 1.0
	if a.State.Energy < 0 {
		a.State.Energy = 0
	}

	// Resting/sleeping recovers energy
	if a.Schedule != nil {
		slot := a.Schedule.CurrentSlot(hour)
		if slot != nil && (slot.Activity == "sleep" || slot.Activity == "wake_up") {
			a.State.Energy += 15.0
			if a.State.Energy > 100 {
				a.State.Energy = 100
			}
		}
	}
}

// Act selects and executes an action, returning it for logging
func (a *Agent) Act(hour int, agentsAtLocation []string, events []string) Action {
	ctx := DecisionContext{
		Agent:            a,
		Events:           make([]interface{}, len(events)),
		Hour:             hour,
		AgentsAtLocation: agentsAtLocation,
	}
	for i, e := range events {
		ctx.Events[i] = e
	}

	action := SelectAction(ctx)

	// Execute energy cost
	switch action.Type {
	case ActionTypeMove:
		a.State.Energy -= 5
	case ActionTypeWork:
		a.State.Energy -= 8
		if a.State.Gold < 100 {
			a.State.Gold += 2
		}
	case ActionTypeRest:
		a.State.Energy += 10
	case ActionTypeSleep:
		a.State.Energy += 20
	case ActionTypeTalk:
		a.State.Energy -= 2
	}

	if a.State.Energy < 0 {
		a.State.Energy = 0
	}
	if a.State.Energy > 100 {
		a.State.Energy = 100
	}

	// Record action in short-term memory
	a.Memory.AddObservation(action.Description, 6.0)

	return action
}

// AddGoal appends a goal to the agent
func (a *Agent) AddGoal(g *Goal) {
	a.Goals = append(a.Goals, g)
}

// AddKnowledge adds a knowledge claim to the agent
func (a *Agent) AddKnowledge(kc *KnowledgeClaim) {
	a.Knowledge = append(a.Knowledge, kc)
}

// UpdateSocialTie adjusts relationship strength with another agent
func (a *Agent) UpdateSocialTie(otherID string, delta float64) {
	current := a.State.SocialTies[otherID]
	newVal := current + delta
	if newVal > 1.0 {
		newVal = 1.0
	}
	if newVal < -1.0 {
		newVal = -1.0
	}
	a.State.SocialTies[otherID] = newVal
}

// Summary returns a human-readable status line
func (a *Agent) Summary() string {
	return fmt.Sprintf("[%s] %s | energy=%.0f mood=%s gold=%d loc=%s",
		a.Identity.Role, a.Identity.Name,
		a.State.Energy, a.State.Mood,
		a.State.Gold, a.State.Location)
}

// Tick advances the agent one game-hour
func (a *Agent) Tick(hour int, agentsAtLocation []string, events []string) Action {
	a.Perceive(events)
	a.Think(hour)
	return a.Act(hour, agentsAtLocation, events)
}

// generateID is a simple ID generator for internal use
func generateID() string {
	return fmt.Sprintf("id_%d", time.Now().UnixNano())
}
