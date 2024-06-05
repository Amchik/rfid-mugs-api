ALTER TABLE users ADD COLUMN telegram_name TEXT DEFAULT NULL;
UPDATE users
    SET telegram_name = (
        SELECT mugs.name
        FROM mugs
        WHERE mugs.owner_id = users.id
        LIMIT 1
    )
    WHERE EXISTS (SELECT 1 FROM mugs WHERE mugs.owner_id = users.id);