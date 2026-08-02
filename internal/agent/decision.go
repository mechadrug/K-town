package agent

import (
	"fmt"
)

// ActionType enumerates possible agent actions
type ActionType string

const (
	ActionTypeMove        ActionType = "move"
	ActionTypeWork        ActionType = "work"
	ActionTypeRest        ActionType = "rest"
	ActionTypeTalk        ActionType = "talk"
	ActionTypeObserve     ActionType = "observe"
	ActionTypeInvestigate ActionType = "investigate"
	ActionTypeTrade       ActionType = "trade"
	ActionTypeSleep       ActionType = "sleep"
)

// Action is a decision output
type Action struct {
	Type        ActionType
	Description string
	Target      string
	Payload     map[string]interface{}
}

// NewAction creates an action with a description
func NewAction(t ActionType, desc string) Action {
	return Action{
		Type:        t,
		Description: desc,
		Target:      "",
		Payload:     make(map[string]interface{}),
	}
}

// DecisionContext holds inputs for decision-making
type DecisionContext struct {
	Agent            *Agent
	Events           []interface{}
	Hour             int
	AgentsAtLocation []string
}

// SelectAction chooses the next action based on rules
func SelectAction(ctx DecisionContext) Action {
	agent := ctx.Agent
	hour := ctx.Hour

	// Rule 1: low energy -> rest
	if agent.State.Energy < 20 {
		return NewAction(ActionTypeRest, fmt.Sprintf("%s is too tired to continue, resting to recover energy", agent.Identity.Name))
	}

	// Rule 2: night time -> sleep
	if hour >= 21 || hour < 6 {
		return NewAction(ActionTypeSleep, fmt.Sprintf("%s is sleeping", agent.Identity.Name))
	}

	// Rule 3: if at scheduled location, perform role task
	if agent.Schedule != nil {
		slot := agent.Schedule.CurrentSlot(hour)
		if slot != nil && agent.State.Location == slot.Location {
			return roleBasedAction(agent, slot)
		}
	}

	// Rule 4: if other agents at location and social drive is high, converse
	if len(ctx.AgentsAtLocation) > 1 {
		if hasTrait(agent, "social") || agent.State.Mood == MoodHappy {
			return NewAction(ActionTypeTalk, fmt.Sprintf("%s starts a conversation", agent.Identity.Name))
		}
	}

	// Rule 5: if interesting events observed, investigate
	if len(ctx.Events) > 0 {
		return NewAction(ActionTypeInvestigate, fmt.Sprintf("%s investigates an event at %s", agent.Identity.Name, agent.State.Location))
	}

	// Rule 6: move toward scheduled location
	if agent.Schedule != nil {
		slot := agent.Schedule.CurrentSlot(hour)
		if slot != nil && agent.State.Location != slot.Location {
			return NewAction(ActionTypeMove, fmt.Sprintf("%s moves to %s", agent.Identity.Name, slot.Location))
		}
	}

	// Default: observe surroundings
	return NewAction(ActionTypeObserve, fmt.Sprintf("%s observes the surroundings", agent.Identity.Name))
}

// roleBasedAction returns an action appropriate for the agent role and current schedule slot
func roleBasedAction(a *Agent, slot *TimeSlot) Action {
	switch slot.Activity {
	case "primary_work", "secondary_work":
		switch a.Identity.Role {
		case RoleBlacksmith:
			return NewAction(ActionTypeWork, fmt.Sprintf("%s forges tools at the workshop", a.Identity.Name))
		case RoleCarpenter:
			return NewAction(ActionTypeWork, fmt.Sprintf("%s crafts wooden items", a.Identity.Name))
		case RoleForager:
			return NewAction(ActionTypeWork, fmt.Sprintf("%s forages for resources", a.Identity.Name))
		case RoleScout:
			return NewAction(ActionTypeWork, fmt.Sprintf("%s scouts the wilderness", a.Identity.Name))
		case RoleFarmer:
			return NewAction(ActionTypeWork, fmt.Sprintf("%s tends the fields", a.Identity.Name))
		case RoleMerchant:
			return NewAction(ActionTypeTrade, fmt.Sprintf("%s trades goods at the square", a.Identity.Name))
		case RoleTeacher:
			return NewAction(ActionTypeTalk, fmt.Sprintf("%s teaches skills to others", a.Identity.Name))
		case RoleStoryteller:
			return NewAction(ActionTypeTalk, fmt.Sprintf("%s tells a story", a.Identity.Name))
		case RoleElder:
			return NewAction(ActionTypeObserve, fmt.Sprintf("%s shares knowledge with passers-by", a.Identity.Name))
		default:
			return NewAction(ActionTypeWork, fmt.Sprintf("%s performs routine work", a.Identity.Name))
		}
	case "lunch_break", "socialize":
		return NewAction(ActionTypeTalk, fmt.Sprintf("%s socializes at the square", a.Identity.Name))
	case "leisure":
		return NewAction(ActionTypeRest, fmt.Sprintf("%s enjoys leisure time", a.Identity.Name))
	default:
		return NewAction(ActionTypeRest, fmt.Sprintf("%s rests", a.Identity.Name))
	}
}

// hasTrait checks if an agent has a specific personality trait
func hasTrait(a *Agent, trait string) bool {
	for _, t := range a.Identity.Traits {
		if t == trait {
			return true
		}
	}
	return false
}

// SelectActionLLM is a placeholder for LLM-driven decision making
// The full implementation will call internal/llm.Client with a constructed prompt
func SelectActionLLM(ctx DecisionContext) Action {
	// TODO: construct prompt from ctx.Agent, ctx.Events, ctx.Hour
	// TODO: call llm.Client.Call(ctx, prompt) and parse response into Action
	// Fallback to rule-based for now
	return SelectAction(ctx)
}
