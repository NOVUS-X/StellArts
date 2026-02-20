// ... other methods ...

/// Get reputation statistics for a user.
/// Returns `(average_scaled_by_100, review_count)`.
/// Example: 9 total stars across 2 reviews → `(450, 2)` (i.e., 4.50 stars).
pub fn get_stats(env: Env, user: Address) -> (u64, u64) {
    let data = read_reputation(&env, &user);
    if data.review_count == 0 {
        return (0, 0);
    }
    let average_scaled = (data.total_stars * 100) / data.review_count;
    (average_scaled, data.review_count)
}

// Remove the duplicate method here.