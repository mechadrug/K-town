package agent

import (
	"sort"
	"time"
)

// TimeSlot maps an hour-of-day to a preferred location
type TimeSlot struct {
	StartHour int
	EndHour   int
	Location  string
	Activity  string
}

// Schedule defines an agent daily routine
type Schedule struct {
	Slots []TimeSlot
}

// NewDefaultSchedule creates the standard daily schedule per world-v0.1.md
func NewDefaultSchedule() *Schedule {
	return &Schedule{
		Slots: []TimeSlot{
			{StartHour: 6, EndHour: 8, Location: "home", Activity: "wake_up"},
			{StartHour: 8, EndHour: 12, Location: "work", Activity: "primary_work"},
			{StartHour: 12, EndHour: 13, Location: "square", Activity: "lunch_break"},
			{StartHour: 13, EndHour: 17, Location: "work", Activity: "secondary_work"},
			{StartHour: 17, EndHour: 19, Location: "square", Activity: "socialize"},
			{StartHour: 19, EndHour: 21, Location: "home", Activity: "leisure"},
			{StartHour: 21, EndHour: 6, Location: "home", Activity: "sleep"},
		},
	}
}

// CurrentSlot returns the schedule slot for a given hour
func (s *Schedule) CurrentSlot(hour int) *TimeSlot {
	for i := range s.Slots {
		slot := &s.Slots[i]
		if slot.StartHour < slot.EndHour {
			if hour >= slot.StartHour && hour < slot.EndHour {
				return slot
			}
		} else {
			// wraps past midnight
			if hour >= slot.StartHour || hour < slot.EndHour {
				return slot
			}
		}
	}
	return nil
}

// Goal represents an agent objective
type Goal struct {
	ID           string
	Description  string
	BasePriority float64
	Urgency      float64
	Deadline     *time.Time
	Completed    bool
}

// ScoredGoal pairs a goal with its computed utility score
type ScoredGoal struct {
	Goal  *Goal
	Score float64
}

// EvaluateGoals ranks an agent goals by utility score
func EvaluateGoals(a *Agent) []ScoredGoal {
	now := time.Now()
	var scored []ScoredGoal

	for _, goal := range a.Goals {
		if goal.Completed {
			continue
		}
		score := goal.BasePriority

		// Urgency modifier
		score += goal.Urgency * 10

		// Deadline proximity modifier
		if goal.Deadline != nil {
			remaining := goal.Deadline.Sub(now).Hours()
			if remaining < 24 {
				score += 20
			} else if remaining < 72 {
				score += 10
			}
		}

		// Low energy reduces work priority, increases rest priority
		if a.State.Energy < 30 {
			if goal.Description == "rest" || goal.Description == "sleep" {
				score += 30
			} else {
				score -= 10
			}
		}

		scored = append(scored, ScoredGoal{Goal: goal, Score: score})
	}

	sort.Slice(scored, func(i, j int) bool {
		return scored[i].Score > scored[j].Score
	})

	return scored
}

// TopGoal returns the highest-scoring active goal
func TopGoal(a *Agent) *Goal {
	scored := EvaluateGoals(a)
	if len(scored) == 0 {
		return nil
	}
	return scored[0].Goal
}
